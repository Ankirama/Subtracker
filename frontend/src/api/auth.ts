import apiClient from './client'
import {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
  TwoFactorRequiredResponse,
  TwoFactorSetupRequest,
  TwoFactorSetupResponse,
  TwoFactorEnableRequest,
  TwoFactorEnableResponse,
  TwoFactorDisableRequest,
  TwoFactorVerifyRequest,
  TwoFactorStatusResponse,
  BackupCodesRegenerateResponse,
  EmailVerificationResponse,
  EmailVerificationRequest,
  ResendVerificationRequest,
  ProfileUpdateRequest,
  PasswordChangeRequest,
  UserPreferencesUpdate,
  DeleteAccountRequest,
  MessageResponse,
  PreferencesResponse,
  LanguagePreferenceUpdate,
  LanguagePreferenceResponse,
} from '../types'

export const authAPI = {
  login: async (credentials: LoginRequest): Promise<TokenResponse | TwoFactorRequiredResponse> => {
    const response = await apiClient.post<TokenResponse | TwoFactorRequiredResponse>('/auth/login', {
      email: credentials.email,
      password: credentials.password,
    })
    return response.data
  },

  register: async (data: RegisterRequest): Promise<EmailVerificationResponse> => {
    const response = await apiClient.post<EmailVerificationResponse>('/auth/register', data)
    return response.data
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me')
    return response.data
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  },

  // Account Management methods

  updateProfile: async (data: ProfileUpdateRequest): Promise<User> => {
    const response = await apiClient.put<User>('/auth/me/profile', data)
    return response.data
  },

  changePassword: async (data: PasswordChangeRequest): Promise<MessageResponse> => {
    const response = await apiClient.put<MessageResponse>('/auth/me/password', data)
    return response.data
  },

  updatePreferences: async (data: UserPreferencesUpdate): Promise<PreferencesResponse> => {
    const response = await apiClient.put<PreferencesResponse>('/auth/me/preferences', data)
    return response.data
  },

  deleteAccount: async (data: DeleteAccountRequest): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>('/auth/me', { data })
    return response.data
  },

  // Two-Factor Authentication methods

  setup2FA: async (data: TwoFactorSetupRequest): Promise<TwoFactorSetupResponse> => {
    const response = await apiClient.post<TwoFactorSetupResponse>('/auth/2fa/setup', data)
    return response.data
  },

  enable2FA: async (data: TwoFactorEnableRequest): Promise<TwoFactorEnableResponse> => {
    const response = await apiClient.post<TwoFactorEnableResponse>('/auth/2fa/enable', data)
    return response.data
  },

  disable2FA: async (data: TwoFactorDisableRequest): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post<{ success: boolean; message: string }>('/auth/2fa/disable', data)
    return response.data
  },

  verify2FALogin: async (data: TwoFactorVerifyRequest): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/auth/2fa/verify-login', data)
    return response.data
  },

  get2FAStatus: async (): Promise<TwoFactorStatusResponse> => {
    const response = await apiClient.get<TwoFactorStatusResponse>('/auth/2fa/status')
    return response.data
  },

  regenerateBackupCodes: async (): Promise<BackupCodesRegenerateResponse> => {
    const response = await apiClient.post<BackupCodesRegenerateResponse>('/auth/2fa/backup-codes/regenerate')
    return response.data
  },

  // Email Verification methods

  verifyEmail: async (data: EmailVerificationRequest): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/auth/verify-email', data)
    return response.data
  },

  resendVerification: async (data: ResendVerificationRequest): Promise<EmailVerificationResponse> => {
    const response = await apiClient.post<EmailVerificationResponse>('/auth/resend-verification', data)
    return response.data
  },

  // Language Preference methods

  getLanguagePreference: async (): Promise<LanguagePreferenceResponse> => {
    const response = await apiClient.get<LanguagePreferenceResponse>('/auth/me/language')
    return response.data
  },

  updateLanguagePreference: async (language: string | null): Promise<LanguagePreferenceResponse> => {
    const response = await apiClient.patch<LanguagePreferenceResponse>('/auth/me/language', {
      language,
    })
    return response.data
  },
}
