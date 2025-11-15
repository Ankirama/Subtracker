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
} from '@chakra-ui/react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'

export const LoginPage = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const { login } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      await login({ email, password })
      toast({
        title: 'Login successful',
        status: 'success',
        duration: 3000,
      })
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Login failed. Please check your credentials.'
      setError(message)
      toast({
        title: 'Login failed',
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
          <Text color="gray.600">Sign in to manage your subscriptions</Text>
        </Box>

        <Box w="full" p={8} borderWidth={1} borderRadius="lg" boxShadow="lg" bg="white">
          <form onSubmit={handleSubmit}>
            <VStack spacing={4}>
              <Heading size="md" alignSelf="start">
                Sign In
              </Heading>

              {error && (
                <Alert status="error" borderRadius="md">
                  <AlertIcon />
                  {error}
                </Alert>
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
        </Box>
      </VStack>
    </Container>
  )
}
