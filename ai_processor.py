import google.generativeai as genai
from google.generativeai import protos
import os
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class GeminiEmailProcessor:
    """Google Gemini AI with Function Calling"""
    
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env file")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            'gemini-2.5-flash',
            tools=self._define_tools()
        )
        
        self.chat_sessions: Dict[int, any] = {}
        self.max_history_per_session = 20
        
        # Kısa system instruction (function calling ile gereksiz detaylar yok)
        self.system_instruction = """You are EmailBot, an email assistant.

When user asks to perform email actions, call the appropriate function.
Keep text responses very brief (1-2 sentences).

Examples:
- "Draft email to John" → Call draft_email()
- "Update draft: add details" → Call update_draft()
- "Show emails from today" → Call fetch_emails()
"""
    
    def _define_tools(self):
        """Function definitions for Gemini"""
        
        return [
            protos.Tool(
                function_declarations=[
                    # 1. DRAFT EMAIL
                    protos.FunctionDeclaration(
                        name='draft_email',
                        description='Create a new email draft',
                        parameters=protos.Schema(
                            type=protos.Type.OBJECT,
                            properties={
                                'recipient': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Recipient name or email address (e.g., "John", "john@company.com")'
                                ),
                                'topic': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Email subject or main topic'
                                ),
                            },
                            required=['recipient', 'topic']
                        )
                    ),
                    
                    # 2. UPDATE DRAFT
                    protos.FunctionDeclaration(
                        name='update_draft',
                        description='Update the existing draft with additional information',
                        parameters=protos.Schema(
                            type=protos.Type.OBJECT,
                            properties={
                                'instruction': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='What to add/change in the draft (e.g., "add budget discussion", "mention Friday deadline")'
                                )
                            },
                            required=['instruction']
                        )
                    ),
                    
                    # 3. FETCH EMAILS
                    protos.FunctionDeclaration(
                        name='fetch_emails',
                        description='Retrieve and display emails based on filters',
                        parameters=protos.Schema(
                            type=protos.Type.OBJECT,
                            properties={
                                'sender': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Filter by sender name (e.g., "boss", "John")'
                                ),
                                'label': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Filter by label/category (e.g., "Work", "Personal", "Promotions")'
                                ),
                                'time_period': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Time filter (e.g., "today", "yesterday", "this_week")'
                                ),
                                'importance': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Filter by importance ("important", "spam", "normal")'
                                )
                            }
                        )
                    ),
                    
                    # 4. MOVE EMAILS
                    protos.FunctionDeclaration(
                        name='move_emails',
                        description='Move emails to a specific folder or label',
                        parameters=protos.Schema(
                            type=protos.Type.OBJECT,
                            properties={
                                'from_sender': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Sender of emails to move'
                                ),
                                'to_folder': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Destination folder (e.g., "Work", "Archive", "Personal")'
                                ),
                                'label': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Filter by label before moving'
                                )
                            },
                            required=['to_folder']
                        )
                    ),
                    
                    # 5. DELETE EMAILS
                    protos.FunctionDeclaration(
                        name='delete_emails',
                        description='Delete emails matching criteria',
                        parameters=protos.Schema(
                            type=protos.Type.OBJECT,
                            properties={
                                'filter': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='What type of emails to delete (e.g., "spam", "old", "unread")'
                                ),
                                'label': protos.Schema(
                                    type=protos.Type.STRING,
                                    description='Delete only from this label'
                                )
                            },
                            required=['filter']
                        )
                    ),
                ]
            )
        ]
    
    def process_command(self, user_input: str, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Process user command with Function Calling"""
        
        try:
            # Get or create chat session
            if session_id not in self.chat_sessions:
                self.chat_sessions[session_id] = self.model.start_chat(history=[])
            
            chat = self.chat_sessions[session_id]
            
            # Add system instruction to first message
            if len(chat.history) == 0:
                full_message = f"{self.system_instruction}\n\nUser: {user_input}"
            else:
                full_message = user_input
            
            # Send message to Gemini
            response = chat.send_message(full_message)
            
            # Trim history if too long
            if len(chat.history) > self.max_history_per_session * 2:
                chat.history = chat.history[-self.max_history_per_session * 2:]
            
            # Check if AI called a function
            if response.candidates[0].content.parts[0].function_call:
                return self._handle_function_call(response, user_input)
            else:
                # Normal text response (casual chat)
                return {
                    'response': response.text,
                    'intent': 'general_chat',
                    'entities': {},
                    'action': {'type': 'chat_only', 'params': {}},
                    'success': True,
                    'model': 'gemini-2.5-flash-fc',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
        except Exception as e:
            print(f"❌ Gemini AI Error: {e}")
            return {
                'response': f"Sorry, I encountered an error: {str(e)}",
                'intent': 'error',
                'entities': {},
                'action': {'type': 'chat_only', 'params': {}},
                'success': False,
                'error': str(e)
            }
    
    def _handle_function_call(self, response, user_input: str) -> Dict[str, Any]:
        """Handle function call from AI"""
        
        function_call = response.candidates[0].content.parts[0].function_call
        function_name = function_call.name
        function_args = dict(function_call.args)
        
        print("\n" + "="*50)
        print(f"🤖 FUNCTION CALLED: {function_name}")
        print(f"📋 Arguments: {function_args}")
        print("="*50 + "\n")
        
        # Map function names to action types
        action_map = {
            'draft_email': 'draft_email',
            'update_draft': 'update_draft',
            'fetch_emails': 'fetch_emails',
            'move_emails': 'move_emails',
            'delete_emails': 'delete_emails'
        }
        
        if function_name not in action_map:
            return {
                'response': f"Unknown function: {function_name}",
                'intent': 'error',
                'entities': {},
                'action': {'type': 'chat_only', 'params': {}},
                'success': False
            }
        
        # Build action
        action = {
            'type': action_map[function_name],
            'params': self._transform_params(function_name, function_args)
        }
        
        # Generate appropriate response text
        response_text = self._generate_response_text(function_name, function_args)
        
        return {
            'response': response_text,
            'intent': function_name,
            'entities': function_args,
            'action': action,
            'success': True,
            'model': 'gemini-2.5-flash-fc',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _transform_params(self, function_name: str, args: Dict) -> Dict:
        """Transform function args to action params"""
        
        if function_name == 'draft_email':
            return {
                'recipient': args.get('recipient', 'Unknown'),
                'topic': args.get('topic', 'No subject'),
                'email_address': args.get('recipient') if '@' in str(args.get('recipient', '')) else None
            }
        
        elif function_name == 'update_draft':
            return {
                'update_instruction': args.get('instruction', '')
            }
        
        elif function_name == 'fetch_emails':
            return {
                'sender': args.get('sender'),
                'label': args.get('label'),
                'time_period': args.get('time_period', 'today'),
                'importance': args.get('importance')
            }
        
        elif function_name == 'move_emails':
            return {
                'from_sender': args.get('from_sender'),
                'to_folder': args.get('to_folder', 'Work'),
                'label': args.get('label')
            }
        
        elif function_name == 'delete_emails':
            return {
                'filter': args.get('filter', 'spam'),
                'label': args.get('label')
            }
        
        return args
    
    def _generate_response_text(self, function_name: str, args: Dict) -> str:
        """Generate user-friendly response text"""
        
        if function_name == 'draft_email':
            recipient = args.get('recipient', 'Unknown')
            topic = args.get('topic', 'No subject')
            return f"✅ Draft created to {recipient} about '{topic}'"
        
        elif function_name == 'update_draft':
            return "✅ Draft updated!"
        
        elif function_name == 'fetch_emails':
            filters = []
            if args.get('sender'):
                filters.append(f"from {args['sender']}")
            if args.get('label'):
                filters.append(f"{args['label']} labeled")
            if args.get('time_period'):
                filters.append(f"from {args['time_period']}")
            
            filter_text = " ".join(filters) if filters else "all"
            return f"📧 Showing emails {filter_text}"
        
        elif function_name == 'move_emails':
            to_folder = args.get('to_folder', 'folder')
            return f"📁 Moving emails to {to_folder}"
        
        elif function_name == 'delete_emails':
            filter_type = args.get('filter', 'emails')
            return f"🗑️ Deleting {filter_type} emails"
        
        return "✅ Action completed"
    
    def clear_history(self, session_id: int):
        """Clear conversation history for a session"""
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]
            print(f"🧹 Cleared conversation history for session {session_id}")
    
    def get_history_length(self, session_id: int) -> int:
        """Get conversation history length"""
        if session_id in self.chat_sessions:
            return len(self.chat_sessions[session_id].history)
        return 0

# Initialize processor with Function Calling
processor = GeminiEmailProcessor()