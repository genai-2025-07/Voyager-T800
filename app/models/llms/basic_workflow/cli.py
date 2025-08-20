#!/usr/bin/env python3
import argparse
import sys
from typing import Optional

from .integration import ItineraryGenerator, save_to_session_history, save_conversation_to_file

class VoyagerCLI:
    """
    CLI for the Basic Workflow of Voyager T800 travel planning assistant.
    """
    def __init__(self, args):
        """
        Initialize the VoyagerCLI.
        Args:
            args: Arguments passed to the CLI.
        """
        self.generator = ItineraryGenerator()
        self.session_history = []
        self.args = args
        self.args.save_history = True
        self.command_handlers = {
            'quit': lambda: "exit",
            'exit': lambda: "exit", 
            'q': lambda: "exit",
            'help': lambda: self._show_help() or "continue",
            'history': lambda: self._show_history() or "continue",
            'save': lambda: self._handle_save_command() or "continue"
        }
        
        self.command_descriptions = {
            'quit': 'Exit the application',
            'exit': 'Exit the application',
            'q': 'Exit the application',
            'help': 'Show this help message',
            'history': 'Show current session history',
            'save': 'Save conversation to file'
        }

        self.command_emojis = {
            'help': '❓',
            'history': '📚',
            'save': '💾',
            'quit': '🚪',
            'exit': '🚪',
            'q': '🚪'
        }
        
        self._validate_command_consistency()
    
    def _save_and_exit(self):
        """
        Save conversation history to file and display exit message.
        
        This method is called when the user exits with save_history enabled.
        It saves the current session history to a file and displays a farewell message.
        """
        if self.session_history:
            print("💾 Saving conversation before exit...")
            save_conversation_to_file(self.session_history)
        print("👋 Thank you for using Voyager T800!")

    def _exit_without_saving(self):
        """
        Display exit message without saving conversation history.
        
        This method is called when the user exits without save_history enabled.
        It displays a farewell message without persisting any data.
        """
        print("👋 Thank you for using Voyager T800!")

    def _exit(self):
        """
        Handle application exit with conditional saving.
        
        Determines whether to save conversation history based on the save_history
        argument and calls the appropriate exit method.
        """
        if self.args.save_history:
            self._save_and_exit()
        else:
            self._exit_without_saving()

    
    def interactive_mode(self):
        """Run the CLI in interactive mode with command parsing and input validation."""
        print("🎯 INTERACTIVE MODE")
        print("Enter your travel request ('quit' to exit; 'help' to see commands):")
        
        while True:
            try:
                user_input = self._get_user_input()
                
                if not self._validate_input(user_input):
                    continue
                
                command_result = self._parse_command(user_input)
                
                if command_result == "exit":
                    self._exit()
                    break
                elif command_result == "continue":
                    continue
                elif command_result == "process":
                    self._process_request(user_input)
                
            except KeyboardInterrupt:
                print("\n⚠️  Interrupted by user")
                self._exit()
                break
            except EOFError:
                print("\n⚠️  End of input reached")
                self._exit()
                break
            except Exception as e:
                print(f"❌ Unexpected error: {str(e)}")
                self._exit()
                break

    def _get_user_input(self) -> str:
        """Get user input from command line arguments or interactive input."""
        if self.args.request:
            user_input = self.args.request
            self.args.request = None
        else:
            user_input = input("\n🌍 Your travel request: ").strip()
        
        return user_input

    def _validate_input(self, user_input: str) -> bool:
        """
        Validate user input for edge cases and empty strings.
        
        Args:
            user_input: The user's input string
            
        Returns:
            bool: True if input is valid, False otherwise
        """
        if not user_input or not user_input.strip():
            print("❌ Please enter a valid travel request.")
            return False
        
        if len(user_input) > 1000:
            print("❌ Input too long. Please keep your request under 1000 characters.")
            return False
        
        return True

    def _parse_command(self, user_input: str) -> str:
        """
        Parse user input to determine if it's a command or travel request.
        
        Args:
            user_input: The user's input string
            
        Returns:
            str: "exit", "continue", or "process" based on command type
        """
        normalized_input = user_input.lower().strip()
        
        if normalized_input in self.command_handlers:
            return self.command_handlers[normalized_input]()
        
        return "process"
    
    def _handle_save_command(self) -> str:
        """
        Handle the save command with proper validation.
        
        Returns:
            str: "continue" after handling save command
        """
        if self.args.save_history:
            self._save_conversation()
        else:
            print("❌ Conversation history will not be saved.")
        return "continue"
    
    def _show_help(self):
        print("\n📖 AVAILABLE COMMANDS:")
        print("=" * 50)
        
        unique_commands = self._get_unique_commands()
        
        for description, commands in unique_commands.items():
            emoji = self._get_command_emoji(commands[0])
            command_list = "/".join(commands)
            print(f"{emoji} {command_list} - {description}")
        
        print("=" * 50)
    
    def _get_unique_commands(self) -> dict:
        """
        Group commands by their descriptions to avoid showing duplicates.
        
        Returns:
            dict: Description -> list of command aliases
        """
        description_to_commands = {}
        
        for command, description in self.command_descriptions.items():
            if description not in description_to_commands:
                description_to_commands[description] = []
            description_to_commands[description].append(command)
        
        return description_to_commands
    
    def _get_command_emoji(self, command: str) -> str:
        """
        Get the emoji associated with a command.
        
        Args:
            command: The command name to get emoji for
            
        Returns:
            str: The emoji for the command, or '🔧' if not found
        """
        return self.command_emojis.get(command, '🔧')
    
    def _validate_command_consistency(self) -> None:
        """
        Validate that command_handlers, command_descriptions, and command_emojis
        have the same keys and length.
        
        This method ensures that all command-related dictionaries are consistent
        and complete. It checks for missing commands in any dictionary and
        raises a ValueError if inconsistencies are found.
        
        Raises:
            ValueError: If the command dictionaries are inconsistent
        """
        handlers_keys = set(self.command_handlers.keys())
        descriptions_keys = set(self.command_descriptions.keys())
        emojis_keys = set(self.command_emojis.keys())
        
        if handlers_keys != descriptions_keys or handlers_keys != emojis_keys:
            missing_in_handlers = descriptions_keys - handlers_keys
            missing_in_descriptions = handlers_keys - descriptions_keys
            missing_in_emojis = handlers_keys - emojis_keys
            extra_in_emojis = emojis_keys - handlers_keys
            
            error_messages = []
            
            if missing_in_handlers:
                error_messages.append(f"Commands missing in handlers: {missing_in_handlers}")
            if missing_in_descriptions:
                error_messages.append(f"Commands missing in descriptions: {missing_in_descriptions}")
            if missing_in_emojis:
                error_messages.append(f"Commands missing in emojis: {missing_in_emojis}")
            if extra_in_emojis:
                error_messages.append(f"Extra commands in emojis: {extra_in_emojis}")
            
            raise ValueError(f"Command dictionaries are inconsistent:\n" + "\n".join(error_messages))
    
    def _show_history(self):
        """
        Display session history and allow user to view specific itineraries.
        
        This method shows the list of available itineraries in the current session
        and provides an interactive interface for users to select and view specific
        itineraries. If no history exists, it displays an appropriate message.
        """
        if not self.session_history:
            print("📭 No itineraries in current session yet.")
            return
        
        self._display_history_list()
        self._handle_history_selection()
    
    def _display_history_list(self):
        """
        Display the list of available itineraries in session history.
        
        This method formats and displays the session history as a numbered list,
        showing timestamps and truncated user inputs for each itinerary entry.
        """
        print(f"\n📚 Current Session History ({len(self.session_history)} itineraries):")
        for i, entry in enumerate(self.session_history, 1):
            truncated_input = entry['user_input'][:50] + "..." if len(entry['user_input']) > 50 else entry['user_input']
            print(f"{i}. {entry['timestamp']} - {truncated_input}")
    
    def _handle_history_selection(self):
        """
        Handle user selection from history with robust input validation and retry loop.
        
        This method provides an interactive interface for users to select specific
        itineraries from the history. It includes input validation, retry logic,
        and graceful error handling for various edge cases.
        
        Features:
        - Maximum 3 attempts for invalid input
        - Support for exit commands ('q', 'quit', 'exit', empty input)
        - Range validation for itinerary selection
        - Graceful handling of keyboard interrupts and EOF
        """
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            try:
                print(f"\n💡 Type a number (1-{len(self.session_history)}) to view that itinerary, or 'q' to exit")
                user_choice = input(f"\n🔍 Your choice (attempt {attempt + 1}/{max_attempts}): ").strip()
                
                if user_choice.lower() in ['q', 'quit', 'exit', '']:
                    print("👋 Returning to main menu...")
                    return
                
                if not user_choice.isdigit():
                    print("❌ Please enter a valid number or 'q' to exit.")
                    attempt += 1
                    continue
                
                index = int(user_choice) - 1
                if not self._is_valid_history_index(index):
                    print(f"❌ Please enter a number between 1 and {len(self.session_history)}.")
                    attempt += 1
                    continue
                
                self._show_itinerary(index)
                return
                
            except KeyboardInterrupt:
                print("\n⚠️  Selection cancelled by user")
                return
            except EOFError:
                print("\n⚠️  End of input reached")
                return
            except Exception as e:
                print(f"❌ Unexpected error: {str(e)}")
                attempt += 1
                continue
        
        print(f"❌ Maximum attempts ({max_attempts}) reached. Returning to main menu...")
    
    def _is_valid_history_index(self, index: int) -> bool:
        """
        Validate if the given index is within the valid range for session history.
        
        Args:
            index: The index to validate
            
        Returns:
            bool: True if index is valid, False otherwise
        """
        return 0 <= index < len(self.session_history)
    
    def _show_itinerary(self, index: int):
        """
        Display a specific itinerary from session history with safe dictionary access and formatting.
        
        This method retrieves and displays a specific itinerary entry from the session
        history. It uses safe dictionary access with .get() methods to prevent KeyError
        exceptions and provides formatted output for better readability.
        
        Args:
            index: The index of the itinerary to display in session_history
        """
        entry = self.session_history[index]
        
        print(f"\n📋 Itinerary #{index + 1} from Session History")
        print("=" * 60)
        
        timestamp = entry.get('timestamp', 'Unknown time')
        user_input = entry.get('user_input', 'No user input available')
        preferences = entry.get('preferences', {})
        itinerary = entry.get('itinerary', 'No itinerary available')
        
        print(f"Time: {timestamp}")
        print(f"User Request: {user_input}")
        print("=" * 60)
        
        if preferences:
            print("Travel Preferences:")
            for key, value in preferences.items():
                formatted_value = self._format_preference_value(value)
                print(f"- {key}: {formatted_value}")
        else:
            print("Travel Preferences: None available")
        
        print("=" * 60)
        print("LLM Response:")
        
        if itinerary is None:
            print("❌ No itinerary available")
            print("This could be due to:")
            print("- LLM service being unavailable")
            print("- Invalid or incomplete travel request")
            print("- API rate limiting or quota exceeded")
            print("- Network connectivity issues")
            print("- Internal processing error")
            print("\n💡 Try again with a different request or check your connection.")
        else:
            self._print_formatted_text(itinerary)
        
        print("=" * 60)
    
    def _format_preference_value(self, value) -> str:
        """
        Format preference values for better display.
        
        This method handles different data types for preference values and formats
        them appropriately for display. It supports None values, dictionaries,
        and raises an error for unsupported types.
        
        Args:
            value: The preference value to format
            
        Returns:
            str: Formatted preference value
            
        Raises:
            ValueError: If the preference value type is not supported
        """
        if value is None:
            return "Not specified"
        elif isinstance(value, dict):
            return "\n".join(f"- {k}: {v}" for k, v in value.items())
        elif isinstance(value, str):
            return value
        else:
            raise ValueError(f"Invalid preference value type: {type(value)}")

    def _print_formatted_text(self, text: str, max_line_length: int = 80):
        """
        Print formatted text with word wrapping and error handling.
        
        This method provides robust text formatting with comprehensive error handling.
        It validates input parameters, handles different text types, and provides
        fallback behavior when formatting fails.
        
        Args:
            text: The text to format and print
            max_line_length: Maximum characters per line (default: 80)
        """
        try:
            if not self._validate_text_input(text):
                return
            
            if not self._validate_line_length(max_line_length):
                max_line_length = 80
            
            if isinstance(text, str):
                self._print_string_text(text, max_line_length)
            else:
                print(f"⚠️  Unexpected text type: {type(text).__name__}")
                print("No content available")
                
        except Exception as e:
            print(f"❌ Error formatting text: {str(e)}")
            print("Displaying raw content:")
            print(str(text)[:200] + "..." if len(str(text)) > 200 else str(text))
    
    def _validate_text_input(self, text) -> bool:
        """
        Validate text input for formatting.
        
        This method performs comprehensive validation of text input before formatting.
        It checks for None values, empty strings, whitespace-only strings, and
        extremely long text that might cause memory issues.
        
        Args:
            text: The text to validate
            
        Returns:
            bool: True if text is valid, False otherwise
        """
        if text is None:
            print("⚠️  Text is None")
            print("No content available")
            return False
        
        if text == "":
            print("No content available")
            return False
        
        if isinstance(text, str) and text.strip() == "":
            print("No content available")
            return False
        
        if isinstance(text, str) and len(text) > 10000:
            print("⚠️  Text is very long, truncating for display")
            text = text[:10000] + "..."
        
        return True
    
    def _validate_line_length(self, max_line_length: int) -> bool:
        """
        Validate maximum line length parameter.
        
        This method validates the max_line_length parameter to ensure it's within
        acceptable bounds for text formatting. It checks type, minimum, and maximum
        values to prevent formatting issues.
        
        Args:
            max_line_length: The line length to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not isinstance(max_line_length, int):
            print(f"⚠️  Invalid line length type: {type(max_line_length).__name__}")
            return False
        
        if max_line_length < 20:
            print(f"⚠️  Line length too short ({max_line_length}), minimum is 20")
            return False
        
        if max_line_length > 200:
            print(f"⚠️  Line length too long ({max_line_length}), maximum is 200")
            return False
        
        return True
    
    def _print_string_text(self, text: str, max_line_length: int):
        """
        Print string text with word wrapping, preserving original newlines.

        This method formats and prints text, preserving original line breaks.
        Each line is wrapped to the specified maximum line length, but explicit
        newlines in the input are not removed or merged. Handles long words and
        provides fallback behavior on error.

        Args:
            text: The string text to format
            max_line_length: Maximum characters per line
        """
        try:
            lines = text.splitlines()
            line_count = 0
            max_lines = 1000

            for original_line in lines:
                words = original_line.split()
                current_line = ""
                for word in words:
                    if line_count >= max_lines:
                        print("⚠️  Text too long, truncating display")
                        return

                    if len(word) > max_line_length:
                        if current_line:
                            print(current_line.rstrip())
                            line_count += 1
                            current_line = ""
                        for i in range(0, len(word), max_line_length - 1):
                            chunk = word[i : i + max_line_length - 1]
                            print(chunk)
                            line_count += 1
                            if line_count >= max_lines:
                                print("⚠️  Text too long, truncating display")
                                return
                        continue

                    if len(current_line) + len(word) + 1 <= max_line_length:
                        current_line += word + " "
                    else:
                        if current_line:
                            print(current_line.rstrip())
                            line_count += 1
                        current_line = word + " "

                if current_line and line_count < max_lines:
                    print(current_line.rstrip())
                    line_count += 1

                if line_count < max_lines:
                    print()
                    line_count += 1
                if line_count >= max_lines:
                    print("⚠️  Text too long, truncating display")
                    return

        except Exception as e:
            print(f"❌ Error processing text: {str(e)}")
            print("Displaying truncated content:")
            print(
                text[:200] + "..." if len(text) > 200 else text
            )
    
    def _save_conversation(self):
        """
        Save the current session history to a file.
        
        This method saves all itineraries in the current session to a file
        for later reference. If no history exists, it displays an appropriate
        message to the user.
        """
        if self.session_history:
            save_conversation_to_file(self.session_history)
            print("💾 Conversation saved to file.")
        else:
            print("📭 No itineraries to save in current session.")
            return
    
    def _process_request(self, user_input: str):
        """
        Process a user's travel request and generate an itinerary.
        
        This method handles the core functionality of generating travel itineraries.
        It calls the LLM service to create a personalized itinerary based on the
        user's input and optionally saves the result to session history.
        
        Args:
            user_input: The user's travel request string
        """
        try:
            print("\n🔄 Generating your personalized itinerary...")
            itinerary = self.generator.generate_enhanced_itinerary(user_input)
            
            print("\n📋 Your Personalized Itinerary:")
            print("=" * 50)
            self._print_formatted_text(itinerary)
            print("=" * 50)

            if self.args.save_history:
                preferences = self.generator.parse_travel_request(user_input)
                self.session_history = save_to_session_history(
                    self.session_history, user_input, itinerary, preferences
                )
            
        except (ValueError, RuntimeError) as e:
            print(f"❌ Error generating itinerary: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error. Try again.")
    
    def single_request(self, user_input: str) -> Optional[str]:
        """
        Process a single travel request without entering interactive mode.
        
        This method is used for non-interactive processing of travel requests.
        It generates an itinerary and saves it to session history, but doesn't
        display the result or enter the interactive loop.
        
        Args:
            user_input: The user's travel request string
            
        Returns:
            Optional[str]: The generated itinerary if successful, None otherwise
        """
        try:
            itinerary = self.generator.generate_enhanced_itinerary(user_input)
            
            preferences = self.generator.parse_travel_request(user_input)
            self.session_history = save_to_session_history(
                self.session_history, user_input, itinerary, preferences
            )
            return itinerary
            
        except Exception as e:
            return None


def start_cli():
    """
    Initialize and start the Voyager T800 CLI application.
    
    This function sets up the command-line argument parser, creates the CLI instance,
    and handles the main application flow. It supports both interactive and
    single-request modes with proper error handling and graceful exit.
    
    Command Line Arguments:
        -r, --request: Process a single travel request and exit
        -i, --interactive: Run in interactive mode (default)
        --save-history: Save conversation history before exit
    
    Raises:
        SystemExit: On successful completion or error conditions
    """
    parser = argparse.ArgumentParser(
        description="Voyager T800 - AI Travel Planning Assistant"
    )
    
    parser.add_argument('-r', '--request', help='Process a single travel request and exit')
    parser.add_argument('-i', '--interactive', action='store_true', help='Run in interactive mode (default)')
    parser.add_argument('--save-history', action='store_true', help='Save conversation history before exit')
    
    args = parser.parse_args()
    
    try:
        cli = VoyagerCLI(args)
        
        if args.request:
            itinerary = cli.single_request(args.request)
            if itinerary:
                print("\n📋 Generated Itinerary:")
                print("=" * 50)
                print(itinerary)
                print("=" * 50)
                
                if args.save_history and cli.session_history:
                    save_conversation_to_file(cli.session_history)
            else:
                print("❌ Failed to generate itinerary")
                sys.exit(1)
        else:
            cli.interactive_mode()
            
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Application error: {str(e)}")
        sys.exit(1)