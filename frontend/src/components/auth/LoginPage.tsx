import { useState } from 'react'
import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Text,
  Link,
  useToast,
  Alert,
  AlertIcon,
  Checkbox,
  HStack,
  IconButton,
} from '@chakra-ui/react'
import { ArrowBackIcon } from '@chakra-ui/icons'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../contexts/AuthContext'
import { authAPI } from '../../api/auth'
import { TwoFactorRequiredResponse } from '../../types'

export const LoginPage = () => {
  // Login form state
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [isUnverifiedError, setIsUnverifiedError] = useState(false)

  // 2FA state
  const [requires2FA, setRequires2FA] = useState(false)
  const [twoFactorMethod, setTwoFactorMethod] = useState<'totp' | 'email'>('totp')
  const [twoFactorMessage, setTwoFactorMessage] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [isBackupCode, setIsBackupCode] = useState(false)
  const [isVerifying, setIsVerifying] = useState(false)

  const { completeLogin } = useAuth()
  const { t } = useTranslation()
  const toast = useToast()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const response = await authAPI.login({ email, password })

      // Check if 2FA is required
      if ('requires_2fa' in response) {
        const twoFactorResponse = response as TwoFactorRequiredResponse
        setRequires2FA(true)
        setTwoFactorMethod(twoFactorResponse.method)
        setTwoFactorMessage(twoFactorResponse.message)
        toast({
          title: t('auth:twoFactor.required'),
          description: twoFactorResponse.message,
          status: 'info',
          duration: 5000,
        })
      } else {
        // Normal login without 2FA
        localStorage.setItem('access_token', response.access_token)
        localStorage.setItem('refresh_token', response.refresh_token)

        toast({
          title: t('auth:login.loginSuccess'),
          status: 'success',
          duration: 3000,
        })

        // Complete login by fetching user into context and navigating
        await completeLogin()
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || t('auth:login.loginFailed')
      const isUnverified = err.response?.status === 403 && message.toLowerCase().includes('not verified')

      setError(message)
      setIsUnverifiedError(isUnverified)
      toast({
        title: isUnverified ? t('auth:verification.failed') : t('auth:login.loginFailed'),
        description: message,
        status: 'error',
        duration: isUnverified ? 7000 : 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleVerify2FA = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsVerifying(true)

    try {
      const response = await authAPI.verify2FALogin({
        email,
        code: verificationCode,
        is_backup_code: isBackupCode,
      })

      // Store tokens
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)

      toast({
        title: t('auth:login.loginSuccess'),
        description: t('auth:twoFactor.verificationSuccess'),
        status: 'success',
        duration: 3000,
      })

      // Complete login by fetching user and navigating
      await completeLogin()
    } catch (err: any) {
      const message = err.response?.data?.detail || t('auth:twoFactor.invalidCode')
      setError(message)
      toast({
        title: t('auth:verification.failed'),
        description: message,
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsVerifying(false)
    }
  }

  const handleBackToLogin = () => {
    setRequires2FA(false)
    setVerificationCode('')
    setIsBackupCode(false)
    setError('')
    setTwoFactorMessage('')
  }

  return (
    <Container maxW="md" py={20}>
      <VStack spacing={8}>
        <Box textAlign="center">
          <Heading size="2xl" mb={2}>
            📧 Subscription Tracker
          </Heading>
          <Text color="text.subtle">
            {requires2FA ? t('auth:twoFactor.enterCode') : t('auth:login.subtitle')}
          </Text>
        </Box>

        <Box w="full" p={8} borderWidth={1} borderRadius="lg" boxShadow="lg" bg="white">
          {!requires2FA ? (
            // Login Form
            <form onSubmit={handleSubmit}>
              <VStack spacing={4}>
                <Heading size="md" alignSelf="start">
                  {t('auth:login.title')}
                </Heading>

                {error && (
                  <>
                    <Alert status="error" borderRadius="md">
                      <AlertIcon />
                      {error}
                    </Alert>
                    {isUnverifiedError && (
                      <Text fontSize="sm" textAlign="center" color="blue.600">
                        <Link as={RouterLink} to="/resend-verification" color="blue.500">
                          {t('auth:register.resendButton')}
                        </Link>
                      </Text>
                    )}
                  </>
                )}

                <FormControl isRequired>
                  <FormLabel>{t('auth:login.emailLabel')}</FormLabel>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                  />
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>{t('auth:login.passwordLabel')}</FormLabel>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t('auth:login.passwordLabel')}
                  />
                </FormControl>

                <Button
                  type="submit"
                  colorScheme="blue"
                  width="full"
                  isLoading={isLoading}
                  loadingText={t('common:messages.loading')}
                >
                  {t('auth:login.loginButton')}
                </Button>

                <Text fontSize="sm">
                  {t('auth:login.noAccount')}{' '}
                  <Link as={RouterLink} to="/register" color="blue.500">
                    {t('auth:login.signUp')}
                  </Link>
                </Text>
              </VStack>
            </form>
          ) : (
            // 2FA Verification Form
            <form onSubmit={handleVerify2FA}>
              <VStack spacing={4}>
                <HStack w="full" justifyContent="space-between" alignItems="center">
                  <IconButton
                    aria-label={t('auth:login.backButton')}
                    icon={<ArrowBackIcon />}
                    onClick={handleBackToLogin}
                    variant="ghost"
                    size="sm"
                  />
                  <Heading size="md">{t('auth:login.twoFactorTitle')}</Heading>
                  <Box w="40px" /> {/* Spacer for alignment */}
                </HStack>

                {twoFactorMessage && (
                  <Alert status="info" borderRadius="md">
                    <AlertIcon />
                    {twoFactorMessage}
                  </Alert>
                )}

                {error && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    {error}
                  </Alert>
                )}

                <FormControl isRequired>
                  <FormLabel>{t('auth:login.codeLabel')}</FormLabel>
                  <Input
                    type="text"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder={isBackupCode ? 'XXXX-XXXX' : '123456'}
                    maxLength={isBackupCode ? 9 : 6}
                    autoFocus
                  />
                  <Text fontSize="xs" color="text.subtle" mt={1}>
                    {t('auth:login.twoFactorSubtitle')}
                  </Text>
                </FormControl>

                <FormControl>
                  <Checkbox
                    isChecked={isBackupCode}
                    onChange={(e) => {
                      setIsBackupCode(e.target.checked)
                      setVerificationCode('')
                    }}
                  >
                    <Text fontSize="sm">{t('auth:twoFactor.usingBackupCode', { defaultValue: 'Using backup code?' })}</Text>
                  </Checkbox>
                </FormControl>

                <Button
                  type="submit"
                  colorScheme="blue"
                  width="full"
                  isLoading={isVerifying}
                  loadingText={t('common:messages.loading')}
                  isDisabled={verificationCode.length < (isBackupCode ? 9 : 6)}
                >
                  {t('auth:login.verifyButton')}
                </Button>

                <Text fontSize="xs" color="gray.500" textAlign="center">
                  {t('auth:twoFactor.backupCodeHint', { defaultValue: 'Backup codes are one-time use codes shown when you enabled 2FA' })}
                </Text>
              </VStack>
            </form>
          )}
        </Box>
      </VStack>
    </Container>
  )
}
