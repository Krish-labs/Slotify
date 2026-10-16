import { createContext } from 'react';
import type { UserResponse } from '../api/types';

export interface AuthContextType {
  user: UserResponse | null;
  token: string | null;
  isLoading: boolean;
  sessionError: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
