#!/usr/bin/env python3
import argparse
import sys
from typing import Optional

from .integration import ItineraryGenerator, save_to_session_history, save_conversation_to_file

class VoyagerCLI:
    def __init__(self, args):
        self.generator = ItineraryGenerator()
        self.session_history = []
        self.args = args
    
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
            
        except (ValueError, RuntimeError) as e:
            print(f"❌ Error generating itinerary: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error. Try again.")
    
    def single_request(self, user_input: str) -> Optional[str]:
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
        sys.exit(1)