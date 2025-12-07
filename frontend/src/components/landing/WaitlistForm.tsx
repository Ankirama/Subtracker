import { useState } from 'react'
import {
  Box,
  Button,
  FormControl,
  FormErrorMessage,
  Input,
  VStack,
  useToast,
  Text,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'
import apiClient from '../../api/client'

interface WaitlistFormProps {
  onSuccess?: () => void
}

export const WaitlistForm = ({ onSuccess }: WaitlistFormProps) => {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const toast = useToast()

  const validateEmail = (email: string) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return re.test(email)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!email.trim()) {
      setError(t('landing:waitlist.invalidEmail'))
      return
    }

    if (!validateEmail(email)) {
      setError(t('landing:waitlist.invalidEmail'))
      return
    }

    try {
      setIsLoading(true)
      await apiClient.post('/api/waitlist', { email: email.toLowerCase().trim() })

      toast({
        title: t('landing:waitlist.successTitle'),
        description: t('landing:waitlist.successMessage'),
        status: 'success',
        duration: 6000,
        isClosable: true,
      })

      setEmail('')
      onSuccess?.()
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || t('landing:waitlist.errorMessage')

      // Handle rate limiting (429 Too Many Requests)
      if (err.response?.status === 429) {
        const retryAfter = err.response?.data?.retry_after || 900 // Default to 15 minutes
        const minutes = Math.ceil(retryAfter / 60)

        toast({
          title: t('landing:waitlist.rateLimitTitle'),
          description: t('landing:waitlist.rateLimitMessage', { minutes }),
          status: 'warning',
          duration: 8000,
          isClosable: true,
        })
      } else if (errorMessage.includes('already on the waitlist')) {
        setError(t('landing:waitlist.alreadyOnList'))
      } else if (errorMessage.includes('already been approved')) {
        setError(t('landing:waitlist.alreadyApproved'))
      } else {
        toast({
          title: t('landing:waitlist.errorTitle'),
          description: errorMessage,
          status: 'error',
          duration: 6000,
          isClosable: true,
        })
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Box as="form" onSubmit={handleSubmit} w="full">
      <VStack spacing={4}>
        <FormControl isInvalid={!!error}>
          <Input
            type="email"
            placeholder={t('landing:waitlist.emailPlaceholder')}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value)
              setError('')
            }}
            size="lg"
            bg="white"
            _dark={{ bg: 'gray.700', borderColor: 'gray.600' }}
            borderColor="gray.300"
            _hover={{ borderColor: 'blue.400' }}
            _focus={{ borderColor: 'blue.500', boxShadow: '0 0 0 1px var(--chakra-colors-blue-500)' }}
            disabled={isLoading}
          />
          {error && (
            <FormErrorMessage>
              <Text fontSize="sm">{error}</Text>
            </FormErrorMessage>
          )}
        </FormControl>

        <Button
          type="submit"
          colorScheme="blue"
          size="lg"
          w="full"
          isLoading={isLoading}
          loadingText={t('landing:waitlist.submit')}
        >
          {t('landing:waitlist.submit')}
        </Button>
      </VStack>
    </Box>
  )
}
