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
      setError('Passwords do not match')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long')
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
        title: 'Registration successful!',
        description: response.message,
        status: 'success',
        duration: 5000,
      })
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Registration failed. Please try again.'
      setError(message)
      toast({
        title: 'Registration failed',
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
            {registrationSuccess ? 'Check your email!' : 'Create your account'}
          </Text>
        </Box>

        <Box w="full" p={8} borderWidth={1} borderRadius="lg" boxShadow="lg" bg="white">
          {registrationSuccess ? (
            // Success message - Email verification required
            <VStack spacing={4}>
              <Heading size="md">📬 Verify Your Email</Heading>

              <Alert status="success" borderRadius="md">
                <AlertIcon />
                Registration successful! Please check your email.
              </Alert>

              <Text textAlign="center">
                We've sent a verification link to <strong>{registeredEmail}</strong>
              </Text>

              <Text fontSize="sm" textAlign="center" color="text.subtle">
                Click the link in your email to verify your account and start using Subscription Tracker.
                The link will expire in 24 hours.
              </Text>

              <Text fontSize="sm" textAlign="center" mt={4}>
                Didn't receive the email?{' '}
                <Link as={RouterLink} to="/resend-verification" color="blue.500">
                  Resend verification email
                </Link>
              </Text>

              <Text fontSize="sm" textAlign="center" mt={2}>
                <Link as={RouterLink} to="/login" color="blue.500">
                  Back to login
                </Link>
              </Text>
            </VStack>
          ) : (
            // Registration form
            <form onSubmit={handleSubmit}>
              <VStack spacing={4}>
                <Heading size="md" alignSelf="start">
                  Register
                </Heading>

                {error && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    {error}
                  </Alert>
                )}

                <FormControl isRequired>
                  <FormLabel>Invite Token</FormLabel>
                  <Input
                    type="text"
                    value={inviteToken}
                    onChange={(e) => setInviteToken(e.target.value)}
                    placeholder="Enter your invite token"
                    isReadOnly={!!searchParams.get('token')}
                    bg={searchParams.get('token') ? 'gray.100' : undefined}
                  />
                  <FormHelperText>
                    Required to register. Get one from an admin.
                  </FormHelperText>
                </FormControl>

                <FormControl>
                  <FormLabel>Display Name (Optional)</FormLabel>
                  <Input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="How should we call you?"
                  />
                  <FormHelperText>Used in personalized emails</FormHelperText>
                </FormControl>

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
                    placeholder="Enter password"
                  />
                  <FormHelperText>At least 8 characters</FormHelperText>
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>Confirm Password</FormLabel>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm password"
                  />
                </FormControl>

                <Button
                  type="submit"
                  colorScheme="blue"
                  width="full"
                  isLoading={isLoading}
                  loadingText="Creating account..."
                >
                  Create Account
                </Button>

                <Text fontSize="sm">
                  Already have an account?{' '}
                  <Link as={RouterLink} to="/login" color="blue.500">
                    Sign in here
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
