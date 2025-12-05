import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { User, LoginRequest, RegisterRequest } from '../types'
import { authAPI } from '../api/auth'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { syncUserLanguagePreference } from '../i18n/detector'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (credentials: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
  completeLogin: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()
  const { i18n } = useTranslation()

  // Check if user is logged in on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token')
      if (token) {
        try {
          const currentUser = await authAPI.getCurrentUser()
          setUser(currentUser)
          // Sync language preference with i18next
          await syncUserLanguagePreference(currentUser.preferred_language || null)
          if (currentUser.preferred_language) {
            await i18n.changeLanguage(currentUser.preferred_language)
          }
        } catch (error) {
          console.error('Failed to fetch user:', error)
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        }
      }
      setIsLoading(false)
    }

    initAuth()
  }, [i18n])

  const login = async (credentials: LoginRequest) => {
    const response = await authAPI.login(credentials)

    // Check if response is TokenResponse (has access_token) or TwoFactorRequiredResponse
    if ('access_token' in response) {
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)

      const currentUser = await authAPI.getCurrentUser()
      setUser(currentUser)
      // Sync language preference with i18next
      await syncUserLanguagePreference(currentUser.preferred_language || null)
      if (currentUser.preferred_language) {
        await i18n.changeLanguage(currentUser.preferred_language)
      }
      navigate('/dashboard')
    }
    // If it's TwoFactorRequiredResponse, the calling component should handle 2FA flow
  }

  const register = async (data: RegisterRequest) => {
    // Register returns EmailVerificationResponse, not tokens
    // User needs to verify email before they can login
    await authAPI.register(data)
    // Don't set tokens or navigate - the calling component should show
    // "check your email" message and handle the verification flow
  }

  const logout = async () => {
    try {
      await authAPI.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      setUser(null)
      navigate('/login')
    }
  }

  const completeLogin = async () => {
    // This is called after 2FA verification when tokens are already in localStorage
    const currentUser = await authAPI.getCurrentUser()
    setUser(currentUser)
    // Sync language preference with i18next
    await syncUserLanguagePreference(currentUser.preferred_language || null)
    if (currentUser.preferred_language) {
      await i18n.changeLanguage(currentUser.preferred_language)
    }
    navigate('/dashboard')
  }

  const value = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    completeLogin,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
