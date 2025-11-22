import { useEffect, useState } from 'react'
import {
  Box,
  Button,
  Container,
  VStack,
  Heading,
  Text,
  Link,
  Alert,
  AlertIcon,
  Spinner,
  Icon,
} from '@chakra-ui/react'
import { CheckCircleIcon, WarningIcon } from '@chakra-ui/icons'
import { Link as RouterLink, useParams, useNavigate } from 'react-router-dom'
import { authAPI } from '../../api/auth'

export const VerifyEmailPage = () => {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [isVerifying, setIsVerifying] = useState(true)
  const [verificationSuccess, setVerificationSuccess] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const verifyEmail = async () => {
      if (!token) {
        setError('Invalid verification link - no token provided')
        setIsVerifying(false)
        return
      }

      try {
        const response = await authAPI.verifyEmail({ token })

        // Store tokens from the response
        localStorage.setItem('access_token', response.access_token)
        localStorage.setItem('refresh_token', response.refresh_token)

        setVerificationSuccess(true)
        setIsVerifying(false)

        // Redirect to dashboard after 3 seconds
        setTimeout(() => {
          navigate('/dashboard')
        }, 3000)
      } catch (err: any) {
        const message = err.response?.data?.detail || 'Verification failed. The link may be invalid or expired.'
        setError(message)
        setIsVerifying(false)
      }
    }

    verifyEmail()
  }, [token, navigate])

  return (
    <Container maxW="md" py={20}>
      <VStack spacing={8}>
        <Box textAlign="center">
          <Heading size="2xl" mb={2}>
            📧 Subscription Tracker
          </Heading>
          <Text color="text.subtle">Email Verification</Text>
        </Box>

        <Box w="full" p={8} borderWidth={1} borderRadius="lg" boxShadow="lg" bg="white">
          <VStack spacing={6}>
            {isVerifying ? (
              // Verifying state
              <>
                <Spinner size="xl" color="blue.500" thickness="4px" />
                <Heading size="md">Verifying your email...</Heading>
                <Text color="text.subtle" textAlign="center">
                  Please wait while we verify your email address
                </Text>
              </>
            ) : verificationSuccess ? (
              // Success state
              <>
                <Icon as={CheckCircleIcon} boxSize={16} color="green.500" />
                <Heading size="md" color="green.600">
                  Email Verified Successfully!
                </Heading>
                <Alert status="success" borderRadius="md">
                  <AlertIcon />
                  Your email has been verified. You're being logged in...
                </Alert>
                <Text color="text.subtle" textAlign="center">
                  Redirecting to your dashboard in a few seconds...
                </Text>
                <Button
                  as={RouterLink}
                  to="/dashboard"
                  colorScheme="blue"
                  size="lg"
                  width="full"
                >
                  Go to Dashboard Now
                </Button>
              </>
            ) : (
              // Error state
              <>
                <Icon as={WarningIcon} boxSize={16} color="red.500" />
                <Heading size="md" color="red.600">
                  Verification Failed
                </Heading>
                <Alert status="error" borderRadius="md">
                  <AlertIcon />
                  {error}
                </Alert>
                <Text color="text.subtle" textAlign="center">
                  The verification link may have expired or is invalid.
                </Text>
                <VStack spacing={3} width="full">
                  <Button
                    as={RouterLink}
                    to="/resend-verification"
                    colorScheme="blue"
                    size="lg"
                    width="full"
                  >
                    Request New Verification Email
                  </Button>
                  <Text fontSize="sm">
                    <Link as={RouterLink} to="/login" color="blue.500">
                      Back to login
                    </Link>
                  </Text>
                </VStack>
              </>
            )}
          </VStack>
        </Box>
      </VStack>
    </Container>
  )
}
