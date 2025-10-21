const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class ApiClient {
  private getHeaders(includeAuth = false): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (includeAuth) {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        headers['Authorization'] = `Bearer ${user.accessToken}`;
      }
    }
    
    return headers;
  }

  async signup(email: string, password: string) {
    const res = await fetch(`${API_BASE_URL}/api/auth/signup`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error('Signup failed');
    return res.json();
  }

  async confirm(email: string, confirmation_code: string) {
    const res = await fetch(`${API_BASE_URL}/api/auth/confirm`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ email, confirmation_code }),
    });
    if (!res.ok) throw new Error('Confirmation failed');
    return res.json();
  }

  async login(email: string, password: string) {
    const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error('Login failed');
    return res.json();
  }

  async refreshToken(refreshToken: string) {
    const res = await fetch(`${API_BASE_URL}/api/auth/refresh-token`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) throw new Error('Token refresh failed');
    return res.json();
  }

  async logoutGlobal() {
    const res = await fetch(`${API_BASE_URL}/api/auth/logout-global`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Global logout failed');
  }

  async createSession(userId?: string) {
    const res = await fetch(`${API_BASE_URL}/api/v1/itinerary/sessions`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({ user_id: userId }),
    });
    if (!res.ok) throw new Error('Failed to create session');
    return res.json();
  }

  async listSessions(userId: string) {
    const res = await fetch(`${API_BASE_URL}/api/v1/itinerary/sessions?user_id=${encodeURIComponent(userId)}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Failed to list sessions');
    return res.json();
  }

  async getSession(sessionId: string, userId: string) {
    const res = await fetch(`${API_BASE_URL}/api/v1/itinerary/${sessionId}?user_id=${encodeURIComponent(userId)}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Failed to get session');
    return res.json();
  }

  async deleteSession(sessionId: string, userId: string) {
    const res = await fetch(`${API_BASE_URL}/api/v1/itinerary/sessions/${sessionId}?user_id=${encodeURIComponent(userId)}`, {
      method: 'DELETE',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Failed to delete session');
  }

  /**
   * Stop ongoing generation for a session
   */
  async stopGeneration(sessionId: string, userId?: string, isGuest = false) {
    const params = new URLSearchParams({ session_id: sessionId });
    if (userId && !isGuest) {
      params.append('user_id', userId);
    }

    const headers: HeadersInit = isGuest 
      ? { 'X-Guest-Mode': 'true' }
      : this.getHeaders(true);

    const res = await fetch(
      `${API_BASE_URL}/api/v1/itinerary/generate/stop?${params}`,
      {
        method: 'POST',
        headers,
      }
    );
    
    if (!res.ok) throw new Error('Failed to stop generation');
    return res.json();
  }

  createStreamConnection(query: string, sessionId?: string, userId?: string, image?: File, isGuest = false) {
    const params = new URLSearchParams({ query });
    if (sessionId) params.append('session_id', sessionId);
    if (userId && !isGuest) params.append('user_id', userId);
    
    const url = `${API_BASE_URL}/api/v1/itinerary/generate/stream?${params}`;
    
    if (image) {
      const formData = new FormData();
      formData.append('image', image);
      
      return fetch(url, {
        method: 'POST',
        headers: {
          ...(isGuest ? {} : { 'Authorization': `Bearer ${JSON.parse(localStorage.getItem('user') || '{}').accessToken}` }),
          ...(isGuest ? { 'X-Guest-Mode': 'true' } : {}),
        },
        body: formData,
      });
    }
    
    const eventSource = new EventSource(url);
    return eventSource;
  }
}

export const apiClient = new ApiClient();
export default apiClient;