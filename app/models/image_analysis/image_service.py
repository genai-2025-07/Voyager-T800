from anthropic import AnthropicBedrock
import os
import logging
import yaml
from pathlib import Path
import xml.etree.ElementTree as ET
from app.utils.read_prompt_from_file import load_prompt_from_file
from app.services.weaviate.attraction_db_manager import AttractionDBManager
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import XMLOutputParser
from langchain_aws import BedrockChat
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

logger = logging.getLogger(__name__)

class ImageService:
    def __init__(self):
        try:
            aws_access_key = os.getenv("AWS_ACCESS_KEY")
            aws_secret_key = os.getenv("AWS_SECRET_KEY")
            aws_session_token = os.getenv("AWS_SESSION_TOKEN")
            aws_region = os.getenv("AWS_REGION")

            self.client = AnthropicBedrock(
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                aws_session_token=aws_session_token,
                aws_region=aws_region or "us-west-2",
            )
        except ValueError:
            logger.error("AWS credentials are not set")
        except TypeError:
            logger.error("Incorrect parameter types passed to AnthropicBedrock constructor")

        self.config = self._get_config()

        if not self.config:
            logger.error("Image recognition config not found")

        if type(self.config) != dict:
            logger.error("Image recognition config is not a dictionary")

        self.attraction_db_manager = AttractionDBManager()
        
        self._init_langchain_components()

    def _get_config(self):
        """
        Loads and returns the image recognition configuration from the YAML file.

        Returns:
            dict: Configuration dictionary loaded from image_recognition_config.yaml.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            yaml.YAMLError: If the YAML file contains invalid syntax.

        Limitations:
            - This method does not perform schema validation on the loaded config.
            - The file path is hardcoded; future improvements could allow injection/configuration.
        """
        config_path = Path("app/config/image_recognition_config.yaml")
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if not isinstance(config, dict):
                raise ValueError("Image recognition config must be a dictionary at the top level.")
            return config

    def _init_langchain_components(self):
        """
        Initialize LangChain components for image analysis.
        
        Creates a ChatAnthropic client and sets up the processing chain
        following LangChain Expression Language (LCEL) patterns.
        
        Limitations:
            - Requires valid AWS credentials for Bedrock access
            - Chain configuration is hardcoded; future improvements could make it configurable
        """
        try:
            self.langchain_llm = BedrockChat(
                model_id=self.config.get("claude_model", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
                model_kwargs={
                    "max_tokens": self.config.get("claude_max_tokens", 1024),
                    "temperature": self.config.get("claude_temperature", 0.1)
                },
                credentials_profile_name=None,
                region_name=os.getenv("AWS_REGION", "us-west-2")
            )
            
            self.xml_parser = XMLOutputParser()
            self._setup_langchain_processing_chain()
            
        except Exception as e:
            logger.error(f"Failed to initialize LangChain components: {e}")
            self.langchain_llm = None
            self.xml_parser = None

    def _setup_langchain_processing_chain(self):
        """
        Set up the LangChain processing chain for image analysis.
        
        Uses LCEL composition pattern to create a predictable pipeline:
        prompt formatting -> LLM processing -> XML parsing -> result extraction
        """
        self.langchain_prompt = ChatPromptTemplate.from_messages([
            ("human", [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": "{image_data}"
                    }
                },
                {
                    "type": "text", 
                    "text": "{prompt_text}"
                }
            ])
        ])
        
        self.langchain_chain = (
            RunnablePassthrough.assign(
                tags_array=lambda _: self.attraction_db_manager.get_unique_tags(),
                prompt_text=lambda x: load_prompt_from_file(self.config["claude_prompt_file"]).format(
                    TAGS_ARRAY=x.get("tags_array", [])
                )
            )
            | self.langchain_prompt
            | self.langchain_llm
            | RunnableLambda(self._parse_xml_response)
        )

    def _parse_xml_response(self, response):
        """
        Parse XML response from LLM into structured format.
        
        Args:
            response: LangChain AIMessage containing XML content
            
        Returns:
            dict: Parsed response with description and tags
        """
        try:
            xml_content = response.content if hasattr(response, 'content') else str(response)
            root = ET.fromstring(xml_content)
            
            result = {}
            description_elem = root.find("description")
            tags_elem = root.find("tags")
            
            if description_elem is not None:
                result["description"] = description_elem.text.strip() if description_elem.text else ""
            else:
                result["description"] = ""
                
            if tags_elem is not None:
                result["tags"] = [tag_elem.text.strip() for tag_elem in tags_elem.findall("tag") if tag_elem.text]
            else:
                result["tags"] = []
                
            return result
        except ET.ParseError as parse_err:
            logger.error(f"Failed to parse XML output: {parse_err}")
            return {"description": "", "tags": []}

    def extract_image_tags(self, image_bytes: bytes):
        """
        Extracts tags from an image using the AnthropicBedrock client and converts the XML output to JSON.

        Args:
            image_bytes (bytes): The image data in bytes.

        Returns:
            dict | None: Parsed JSON object containing image description and tags, or None on failure.

        Limitations:
            - Assumes the LLM always returns well-formed XML in the expected format.
            - No schema validation is performed on the parsed JSON.
            - Only supports images in JPEG format; future improvements could generalize this.
            - Error handling is basic; future improvements could provide more granular error reporting.
        """
        if not self.client:
            logger.error("AnthropicBedrock client not initialized")
            return None
        if not image_bytes:
            logger.error("Image bytes data is not set")
            return None
        if type(image_bytes) != bytes:
            logger.error("Image bytes data is not a bytes object")
            return None

        try:
            prompt = load_prompt_from_file(self.config["claude_prompt_file"])
            tags_array = self.attraction_db_manager.get_unique_tags()
            prompt = prompt.format(TAGS_ARRAY=tags_array)
            message = self.client.messages.create(
                model=self.config["claude_model"],
                max_tokens=self.config["claude_max_tokens"],
                temperature=self.config["claude_temperature"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_bytes,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )
        except Exception as e:
            logger.error(f"Error recognizing image: {e}")
            return None

        xml_content = message.content if hasattr(message, "content") else None
        if not xml_content or not isinstance(xml_content, str):
            logger.error("No XML content returned from LLM")
            return None

        try:
            root = ET.fromstring(xml_content)
            result = {}
            description_elem = root.find("description")
            tags_elem = root.find("tags")
            if description_elem is not None:
                result["description"] = description_elem.text.strip() if description_elem.text else ""
            else:
                result["description"] = ""
            if tags_elem is not None:
                result["tags"] = [tag_elem.text.strip() for tag_elem in tags_elem.findall("tag") if tag_elem.text]
            else:
                result["tags"] = []
            return result
        except ET.ParseError as parse_err:
            logger.error(f"Failed to parse XML output: {parse_err}")
            return None

    def extract_image_tags_langchain(self, image_bytes: bytes):
        """
        Extracts tags from an image using LangChain approach with LCEL composition.
        
        This method demonstrates the LangChain Expression Language (LCEL) pattern
        for composing AI workflows, following the project's architectural principles.
        
        Args:
            image_bytes (bytes): The image data in bytes.
            
        Returns:
            dict | None: Parsed JSON object containing image description and tags, or None on failure.
            
        Limitations:
            - Requires LangChain components to be properly initialized
            - Only supports images in JPEG format; future improvements could generalize this
            - Chain composition is predefined; future improvements could allow dynamic configuration
            - Error handling focuses on chain execution; individual component errors may not be detailed
        """
        if not hasattr(self, 'langchain_chain') or self.langchain_chain is None:
            logger.error("LangChain components not initialized")
            return None
            
        if not image_bytes:
            logger.error("Image bytes data is not set")
            return None
            
        if not isinstance(image_bytes, bytes):
            logger.error("Image bytes data is not a bytes object")
            return None
            
        try:
            # Use the LangChain processing chain with LCEL composition
            result = self.langchain_chain.invoke({
                "image_data": image_bytes
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing image with LangChain: {e}")
            return None