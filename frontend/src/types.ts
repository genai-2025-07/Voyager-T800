export interface User {
  sub: string;
  email: string;
  accessToken: string;
  idToken: string;
  expiresAt: number;
}


export interface Message {
  sender: 'user' | 'assistant';
  content: string;
  image_url?: string;
  image_url_expires_at?: string;
  image_error?: string;
  timestamp: number;
}

export interface Session {
  session_id: string;
  user_id?: string;
  started_at: string;
  summary?: string;
  messages?: Message[];
}