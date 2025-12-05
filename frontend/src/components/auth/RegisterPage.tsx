import { useState, useEffect } from 'react'
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
  FormHelperText,
} from '@chakra-ui/react'
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { authAPI } from '../../api/auth'

export const RegisterPage = () => {
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [inviteToken, setInviteToken] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [registrationSuccess, setRegistrationSuccess] = useState(false)
  const [registeredEmail, setRegisteredEmail] = useState('')
  const navigate = useNavigate()
  const { t } = useTranslation()
  const toast = useToast()

  // Pre-fill invite token from URL query param
  useEffect(() => {
    const token = searchParams.get('token')
    if (token) {
      setInviteToken(token)
    }
  }, [searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validation
    if (password !== confirmPassword) {
      setError(t('common:validation.passwordMismatch'))
      return
    }

    if (password.length < 8) {
      setError(t('common:validation.passwordTooShort'))
      return
    }

    setIsLoading(true)

    try {
      const response = await authAPI.register({
        email,
        password,
        display_name: displayName || undefined,
        invite_token: inviteToken || undefined,
      })

      // Show success message and email verification instructions
      setRegistrationSuccess(true)
      setRegisteredEmail(response.email)
      toast({
        title: t('auth:register.registrationSuccess'),
        description: response.message,
        status: 'success',
        duration: 5000,
      })
    } catch (err: any) {
      const message = err.response?.data?.detail || t('auth:register.registrationFailed')
      setError(message)
      toast({
        title: t('auth:register.registrationFailed'),
        description: message,
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Container maxW="md" py={20}>
      <VStack spacing={8}>
        <Box textAlign="center">
          <Heading size="2xl" mb={2}>
            📧 Subscription Tracker
          </Heading>
          <Text color="text.subtle">
            {registrationSuccess ? t('auth:register.verifyEmailTitle') : t('auth:register.subtitle')}
          </Text>
        </Box>

        <Box w="full" p={8} borderWidth={1} borderRadius="lg" boxShadow="lg" bg="white">
          {registrationSuccess ? (
            // Success message - Email verification required
            <VStack spacing={4}>
              <Heading size="md">📬 {t('auth:register.verifyEmailTitle')}</Heading>

              <Alert status="success" borderRadius="md">
                <AlertIcon />
                {t('auth:register.registrationSuccess')}
              </Alert>

              <Text textAlign="center">
                {t('auth:register.verifyEmailMessage', { email: registeredEmail })}
              </Text>

              <Text fontSize="sm" textAlign="center" mt={4}>
                {t('auth:register.verifyEmailNote')}{' '}
                <Link as={RouterLink} to="/resend-verification" color="blue.500">
                  {t('auth:register.resendButton')}
                </Link>
              </Text>

              <Text fontSize="sm" textAlign="center" mt={2}>
                <Link as={RouterLink} to="/login" color="blue.500">
                  {t('auth:register.backButton')}
                </Link>
              </Text>
            </VStack>
          ) : (
            // Registration form
            <form onSubmit={handleSubmit}>
              <VStack spacing={4}>
                <Heading size="md" alignSelf="start">
                  {t('auth:register.title')}
                </Heading>

                {error && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    {error}
                  </Alert>
                )}

                <FormControl isRequired>
                  <FormLabel>{t('auth:register.inviteTokenLabel')}</FormLabel>
                  <Input
                    type="text"
                    value={inviteToken}
                    onChange={(e) => setInviteToken(e.target.value)}
                    placeholder={t('auth:register.inviteTokenPlaceholder')}
                    isReadOnly={!!searchParams.get('token')}
                    bg={searchParams.get('token') ? 'gray.100' : undefined}
                  />
                  <FormHelperText>
                    {t('auth:register.inviteTokenHelp', { defaultValue: 'Required to register. Get one from an admin.' })}
                  </FormHelperText>
                </FormControl>

                <FormControl>
                  <FormLabel>{t('auth:register.displayNameLabel')}</FormLabel>
                  <Input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder={t('auth:register.displayNamePlaceholder')}
                  />
                  <FormHelperText>{t('auth:register.displayNameHelp', { defaultValue: 'Used in personalized emails' })}</FormHelperText>
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>{t('auth:register.emailLabel')}</FormLabel>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                  />
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>{t('auth:register.passwordLabel')}</FormLabel>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t('auth:register.passwordLabel')}
                  />
                  <FormHelperText>{t('auth:register.passwordHelp', { defaultValue: 'At least 8 characters' })}</FormHelperText>
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>{t('auth:register.confirmPasswordLabel', { defaultValue: 'Confirm Password' })}</FormLabel>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder={t('auth:register.confirmPasswordLabel', { defaultValue: 'Confirm password' })}
                  />
                </FormControl>

                <Button
                  type="submit"
                  colorScheme="blue"
                  width="full"
                  isLoading={isLoading}
                  loadingText={t('common:messages.loading')}
                >
                  {t('auth:register.registerButton')}
                </Button>

                <Text fontSize="sm">
                  {t('auth:register.hasAccount')}{' '}
                  <Link as={RouterLink} to="/login" color="blue.500">
                    {t('auth:register.signIn')}
                  </Link>
                </Text>
              </VStack>
            </form>
          )}
        </Box>
      </VStack>
    </Container>
  )
}
