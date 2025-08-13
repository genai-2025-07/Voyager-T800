#!/usr/bin/env python3
import argparse
import sys
import os
from typing import Optional

from app.config.logging_config import get_logger
from .integration import ItineraryGenerator, save_to_session_history, save_conversation_to_file
from app.services.itinerary_storage import ItineraryStorage

logger = get_logger("voyager_t800.cli")


class VoyagerCLI:
    def __init__(self, args):
        self.generator = ItineraryGenerator()
        self.session_history = []
        self.args = args
        self.storage = ItineraryStorage()
    
    def _save_and_exit(self):
        if self.session_history:
            print("💾 Saving conversation before exit...")
            save_conversation_to_file(self.session_history)
        print("👋 Thank you for using Voyager T800!")

    def _exit_without_saving(self):
        print("👋 Thank you for using Voyager T800!")

    def _exit(self):
        if not self.args.not_save_history:
            self._save_and_exit()
        else:
            self._exit_without_saving()

    
    def interactive_mode(self):
        print("🎯 INTERACTIVE MODE")
        print("Enter your travel request ('quit' to exit; 'help' to see commands):")
        
        while True:
            try:
                user_input = ''
                if self.args.request:
                    user_input = self.args.request
                else:
                    user_input = input("\n🌍 Your travel request: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    self._exit()
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                if user_input.lower() == 'history':
                    self._show_history()
                    continue
                
                if user_input.lower() == 'save' and not self.args.not_save_history:
                    self._save_conversation()
                    continue
                elif user_input.lower() == 'save' and self.args.not_save_history:
                    print("❌ Conversation history will not be saved.")
                    continue
                
                if user_input.lower() == 'export':
                    self._export_last_itinerary()
                    continue
                
                if user_input.lower() == 'export-all':
                    self._export_all_itineraries()
                    continue
                
                if user_input.lower() == 'list-json':
                    self._list_json_itineraries()
                    continue
                
                if user_input.lower() == 'search-json':
                    self._search_json_by_user_id()
                    continue
                
                if not user_input:
                    print("❌ Please enter a valid travel request.")
                    continue
                
                self._process_request(user_input)
                
            except Exception:
                self._exit()
                break
    
    def _show_help(self):
        print("\n📖 AVAILABLE COMMANDS:")
        print("=" * 50)
        print("📚 history - Show current session history")
        print("💾 save - Save conversation to file")
        print("📄 export - Export last itinerary as JSON")
        print("📋 export-all - Export all itineraries in history as JSON")
        print("📋 list-json - List all saved JSON itineraries")
        print("🔍 search-json - Search JSON itineraries by user ID")
        print("❓ help - Show this help message")
        print("🚪 quit/exit/q - Exit the application")
        print("=" * 50)
    
    def _show_history(self):
        if not self.session_history:
            print("📭 No itineraries in current session yet.")
            return
        
        print(f"\n📚 Current Session History ({len(self.session_history)} itineraries):")
        for i, entry in enumerate(self.session_history, 1):
            print(f"{i}. {entry['timestamp']} - {entry['user_input'][:50]}...")
        
        print("\n💡 Type a number (e.g., '1') to view that itinerary, or any letter to exit")
        user_choice = input("\n🔍 Your choice: ").strip()
        
        if user_choice.isdigit():
            try:
                index = int(user_choice) - 1
                if 0 <= index < len(self.session_history):
                    self._show_itinerary(index)
                else:
                    return
            except ValueError:
                print("❌ Please enter a valid number.")
    
    def _show_itinerary(self, index: int):
        entry = self.session_history[index]
        print(f"\n📋 Itinerary #{index + 1} from Session History")
        print("=" * 60)
        print(f"Time: {entry['timestamp']}")
        print(f"User Request: {entry['user_input']}")
        print("=" * 60)
        print("Travel Preferences:")
        for key, value in entry['preferences'].items():
            print(f"- {key}: {value}")
        print("=" * 60)
        print("LLM Response:")
        print(entry['itinerary'])
        print("=" * 60)
    
    def _save_conversation(self):
        if self.session_history:
            save_conversation_to_file(self.session_history)
            print("💾 Conversation saved to file.")
        else:
            print("📭 No itineraries to save in current session.")
            return
    
    def _export_last_itinerary(self):
        if not self.session_history:
            print("📭 No itineraries to export in current session.")
            return
        
        try:
            last_entry = self.session_history[-1]
            
            itinerary_data = self.storage.create_itinerary_json(
                user_input=last_entry['user_input'],
                itinerary_text=last_entry['itinerary'],
                preferences=last_entry['preferences']
            )
            
            filepath = self.storage.save_itinerary(itinerary_data)
            
            print(f"📄 Itinerary exported to JSON: {filepath}")
            print(f"📋 Session ID: {itinerary_data['user_id']}")
            
        except Exception as e:
            print(f"❌ Failed to export itinerary: {str(e)}")
            logger.error(f"Failed to export itinerary: {str(e)}")
    
    def _export_all_itineraries(self):
        if not self.session_history:
            print("📭 No itineraries to export in current session.")
            return
        try:
            exported_count = 0
            print(f"\n📄 Exporting {len(self.session_history)} itineraries as JSON...")
            
            for i, entry in enumerate(self.session_history, 1):
                try:
                    itinerary_data = self.storage.create_itinerary_json(
                        user_input=entry['user_input'],
                        itinerary_text=entry['itinerary'],
                        preferences=entry['preferences'],
                        session_id=f"session_{i:03d}"
                    )
                    
                    filename = f"itinerary_{i:03d}_{itinerary_data['user_id']}.json"
                    filepath = self.storage.save_itinerary(itinerary_data, filename)
                    
                    print(f"  ✅ Exported itinerary #{i}: {os.path.basename(filepath)}")
                    exported_count += 1
                    
                except Exception as e:
                    print(f"  ❌ Failed to export itinerary #{i}: {str(e)}")
                    logger.error(f"Failed to export itinerary #{i}: {str(e)}")

                # Because of the LLM approach, we may fail to preserve history
                print(f"📊 Export Summary:")
                print(f"Total itineraries: {len(self.session_history)}")
                print(f"Successfully exported: {exported_count}")
                print(f"Failed: {len(self.session_history) - exported_count}")
            
            if exported_count > 0:
                print(f"    📁 Files saved in: {self.storage.storage_dir}")
            
        except Exception as e:
            print(f"❌ Failed to export itineraries: {str(e)}")
            logger.error(f"Failed to export all itineraries: {str(e)}")
    
    def _list_json_itineraries(self):
        try:
            files = self.storage.list_itineraries()
            
            if not files:
                print("📭 No saved JSON itineraries found.")
                return
            
            print(f"\n📋 Saved JSON Itineraries ({len(files)} files):")
            print("=" * 60)
            
            for i, filepath in enumerate(files, 1):
                filename = os.path.basename(filepath)
                print(f"{i}. {filename}")
            
            print("\n💡 Type a number to load that itinerary, or any letter to exit")
            user_choice = input("\n🔍 Your choice: ").strip()
            
            if user_choice.isdigit():
                try:
                    index = int(user_choice) - 1
                    if 0 <= index < len(files):
                        self._load_json_itinerary(files[index])
                    else:
                        print(f"❌ Invalid number. Please enter a number between 1 and {len(files)}.")
                except ValueError:
                    print("❌ Please enter a valid number.")
                    
        except Exception as e:
            print(f"❌ Failed to list itineraries: {str(e)}")
            logger.error(f"Failed to list itineraries: {str(e)}")
    
    def _load_json_itinerary(self, filepath: str):
        try:
            itinerary_data = self.storage.load_itinerary(filepath)
            
            print(f"\n📋 Loaded Itinerary from JSON")
            print("=" * 60)
            print(f"Session ID: {itinerary_data.get('user_id', 'Unknown')}")
            print(f"Timestamp: {itinerary_data.get('timestamp', 'Unknown')}")
            print(f"Duration: {itinerary_data.get('trip_duration', 'Unknown')}")
            print(f"Destinations: {', '.join(itinerary_data.get('destinations', []))}")
            print(f"Budget: {itinerary_data.get('budget', 'Unknown')}")
            print(f"Travel Style: {itinerary_data.get('travel_style', 'Unknown')}")
            print(f"Preferences: {', '.join(itinerary_data.get('preferences', []))}")
            print("=" * 60)
            
            days = itinerary_data.get('days', [])
            if days:
                print("\n📅 Day-by-Day Structure:")
                for day in days:
                    print(f"\nDay {day.get('day', '?')} - {day.get('city', 'Unknown')}")
                    activities = day.get('activities', [])
                    for activity in activities:
                        print(f"  • {activity}")
            
            print("=" * 60)
            
        except Exception as e:
            print(f"❌ Failed to load itinerary: {str(e)}")
            logger.error(f"Failed to load itinerary {filepath}: {str(e)}")
    
    def _search_json_by_user_id(self):
        try:
            user_id = input("\n🔍 Enter user ID to search for (e.g., session_001): ").strip()
            
            if not user_id: 
                print("❌ Please enter a valid user ID.")
                return
            
            filepath = self.storage.find_itinerary_by_session(user_id)
            
            if filepath:
                print(f"✅ Found itinerary for user ID: {user_id}")
                print(f"📁 File: {os.path.basename(filepath)}")
                
                self._load_json_itinerary(filepath)
            else:
                print(f"📭 No itinerary found for user ID: {user_id}")
                
        except Exception as e:
            print(f"❌ Failed to search for itinerary: {str(e)}")
            logger.error(f"Failed to search for itinerary: {str(e)}")
    
    def _process_request(self, user_input: str):
        try:
            print("\n🔄 Generating your personalized itinerary...")
            itinerary = self.generator.generate_enhanced_itinerary(user_input)
            
            print("\n📋 Your Personalized Itinerary:")
            print("=" * 50)
            print(itinerary)
            print("=" * 50)

            if not self.args.not_save_history:
                preferences = self.generator.parse_travel_request(user_input)
                self.session_history = save_to_session_history(
                    self.session_history, user_input, itinerary, preferences
                )
                logger.info(f"💾 Added to session history (total: {len(self.session_history)})")
            
        except (ValueError, RuntimeError) as e:
            print(f"❌ Error generating itinerary: {str(e)}")
            logger.error(f"Itinerary generation error: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error. Try again.")
            logger.error(f"Unexpected error in request processing: {str(e)}")
    
    def single_request(self, user_input: str) -> Optional[str]:
        try:
            logger.info(f"Processing single request: {user_input}")
            itinerary = self.generator.generate_enhanced_itinerary(user_input)
            
            preferences = self.generator.parse_travel_request(user_input)
            self.session_history = save_to_session_history(
                self.session_history, user_input, itinerary, preferences
            )
            return itinerary
            
        except Exception as e:
            logger.error(f"Error processing single request: {str(e)}")
            return None


def start_cli():
    parser = argparse.ArgumentParser(
        description="Voyager T800 - AI Travel Planning Assistant"
    )
    
    parser.add_argument('-r', '--request', help='Process a single travel request and exit')
    parser.add_argument('-i', '--interactive', action='store_true', help='Run in interactive mode (default)')
    parser.add_argument('--not-save-history', action='store_true', help='Do not save conversation history before exit')
    
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
        logger.error(f"Application error: {str(e)}")
        sys.exit(1)