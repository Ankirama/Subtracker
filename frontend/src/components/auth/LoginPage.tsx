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
          title: '2FA Required',
          description: twoFactorResponse.message,
          status: 'info',
          duration: 5000,
        })
      } else {
        // Normal login without 2FA
        localStorage.setItem('access_token', response.access_token)
        localStorage.setItem('refresh_token', response.refresh_token)

        // Get current user and navigate
        const currentUser = await authAPI.getCurrentUser()
        toast({
          title: 'Login successful',
          status: 'success',
          duration: 3000,
        })
        navigate('/dashboard')
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Login failed. Please check your credentials.'
      const isUnverified = err.response?.status === 403 && message.toLowerCase().includes('not verified')

      setError(message)
      setIsUnverifiedError(isUnverified)
      toast({
        title: isUnverified ? 'Email not verified' : 'Login failed',
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
        title: 'Login successful',
        description: '2FA verification completed',
        status: 'success',
        duration: 3000,
      })

      // Complete login by fetching user and navigating
      await completeLogin()
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Invalid verification code'
      setError(message)
      toast({
        title: 'Verification failed',
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
            {requires2FA ? 'Enter verification code' : 'Sign in to manage your subscriptions'}
          </Text>
        </Box>

        <Box w="full" p={8} borderWidth={1} borderRadius="lg" boxShadow="lg" bg="white">
          {!requires2FA ? (
            // Login Form
            <form onSubmit={handleSubmit}>
              <VStack spacing={4}>
                <Heading size="md" alignSelf="start">
                  Sign In
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
                          Click here to resend verification email
                        </Link>
                      </Text>
                    )}
                  </>
                )}

                <FormControl isRequired>
                  <FormLabel>Email</FormLabel>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                  />
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>Password</FormLabel>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                  />
                </FormControl>

                <Button
                  type="submit"
                  colorScheme="blue"
                  width="full"
                  isLoading={isLoading}
                  loadingText="Signing in..."
                >
                  Sign In
                </Button>

                <Text fontSize="sm">
                  Don't have an account?{' '}
                  <Link as={RouterLink} to="/register" color="blue.500">
                    Register here
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
                    aria-label="Back to login"
                    icon={<ArrowBackIcon />}
                    onClick={handleBackToLogin}
                    variant="ghost"
                    size="sm"
                  />
                  <Heading size="md">Two-Factor Authentication</Heading>
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
                  <FormLabel>
                    {twoFactorMethod === 'totp'
                      ? 'Authenticator Code'
                      : 'Email Verification Code'}
                  </FormLabel>
                  <Input
                    type="text"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder={isBackupCode ? 'XXXX-XXXX' : '123456'}
                    maxLength={isBackupCode ? 9 : 6}
                    autoFocus
                  />
                  <Text fontSize="xs" color="text.subtle" mt={1}>
                    {twoFactorMethod === 'totp'
                      ? 'Enter the 6-digit code from your authenticator app'
                      : 'Enter the 6-digit code sent to your email'}
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
                    <Text fontSize="sm">Using backup code?</Text>
                  </Checkbox>
                </FormControl>

                <Button
                  type="submit"
                  colorScheme="blue"
                  width="full"
                  isLoading={isVerifying}
                  loadingText="Verifying..."
                  isDisabled={verificationCode.length < (isBackupCode ? 9 : 6)}
                >
                  Verify & Sign In
                </Button>

                <Text fontSize="xs" color="gray.500" textAlign="center">
                  Backup codes are one-time use codes shown when you enabled 2FA
                </Text>
              </VStack>
            </form>
          )}
        </Box>
      </VStack>
    </Container>
  )
}
