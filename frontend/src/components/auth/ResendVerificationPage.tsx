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
  FormHelperText,
} from '@chakra-ui/react'
import { Link as RouterLink } from 'react-router-dom'
import { authAPI } from '../../api/auth'

export const ResendVerificationPage = () => {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const toast = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess(false)

    if (!email) {
      setError('Please enter your email address')
      return
    }

    setIsLoading(true)

    try {
      const response = await authAPI.resendVerification({ email })

      setSuccess(true)
      toast({
        title: 'Verification email sent!',
        description: response.message,
        status: 'success',
        duration: 5000,
      })
    } catch (err: any) {
      // Check for rate limiting error
      const message = err.response?.data?.detail || 'Failed to send verification email. Please try again.'
      const isRateLimited = err.response?.status === 429

      setError(message)
      toast({
        title: isRateLimited ? 'Too many requests' : 'Failed to send email',
        description: message,
        status: 'error',
        duration: isRateLimited ? 7000 : 5000,
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
          <Text color="text.subtle">Resend Verification Email</Text>
        </Box>

        <Box w="full" p={8} borderWidth={1} borderRadius="lg" boxShadow="lg" bg="white">
          {success ? (
            // Success message
            <VStack spacing={4}>
              <Heading size="md">📬 Check Your Email</Heading>

              <Alert status="success" borderRadius="md">
                <AlertIcon />
                Verification email sent successfully!
              </Alert>

              <Text textAlign="center">
                If an account with email <strong>{email}</strong> exists and is unverified,
                you'll receive a verification email shortly.
              </Text>

              <Text fontSize="sm" textAlign="center" color="text.subtle">
                Check your inbox and click the verification link. The link will expire in 24 hours.
              </Text>

              <Text fontSize="sm" textAlign="center" mt={4}>
                <Link as={RouterLink} to="/login" color="blue.500">
                  Back to login
                </Link>
              </Text>
            </VStack>
          ) : (
            // Resend form
            <form onSubmit={handleSubmit}>
              <VStack spacing={4}>
                <Heading size="md" alignSelf="start">
                  Resend Verification
                </Heading>

                <Text fontSize="sm" color="text.subtle">
                  Enter your email address and we'll send you a new verification link.
                </Text>

                {error && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    {error}
                  </Alert>
                )}

                <FormControl isRequired>
                  <FormLabel>Email Address</FormLabel>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                    autoFocus
                  />
                  <FormHelperText>
                    We'll send a verification link to this email
                  </FormHelperText>
                </FormControl>

                <Button
                  type="submit"
                  colorScheme="blue"
                  width="full"
                  isLoading={isLoading}
                  loadingText="Sending..."
                >
                  Send Verification Email
                </Button>

                <Text fontSize="sm">
                  Remember your password?{' '}
                  <Link as={RouterLink} to="/login" color="blue.500">
                    Back to login
                  </Link>
                </Text>

                <Text fontSize="sm">
                  Don't have an account?{' '}
                  <Link as={RouterLink} to="/register" color="blue.500">
                    Register here
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
