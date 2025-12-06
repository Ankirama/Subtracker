import { useState, useEffect } from 'react'
import {
  VStack,
  Heading,
  FormControl,
  FormLabel,
  Select,
  Input,
  Button,
  useToast,
  Card,
  CardBody,
  CardHeader,
  Text,
} from '@chakra-ui/react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { authAPI } from '../../api/auth'
import type { UserPreferencesUpdate } from '../../types'
import { LanguageSwitcher } from '../common/LanguageSwitcher'

export function PreferencesTab() {
  const toast = useToast()

  // For simplicity, we'll fetch current user preferences from the user settings
  // In a real app, you might want a dedicated endpoint for preferences
  const { data: currentUser } = useQuery({
    queryKey: ['currentUser'],
    queryFn: authAPI.getCurrentUser,
  })

  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system')
  const [language, setLanguage] = useState('en')
  const [currency, setCurrency] = useState('USD')
  const [dateFormat, setDateFormat] = useState('MM/DD/YYYY')
  const [timezone, setTimezone] = useState('UTC')

  // Load current preferences when user data is available
  useEffect(() => {
    if (currentUser) {
      // Assuming preferences are stored in user.settings or similar
      // Adjust based on actual backend implementation
      const prefs = (currentUser as any).settings || {}
      if (prefs.theme) setTheme(prefs.theme)
      if (prefs.language) setLanguage(prefs.language)
      if (prefs.currency) setCurrency(prefs.currency)
      if (prefs.date_format) setDateFormat(prefs.date_format)
      if (prefs.timezone) setTimezone(prefs.timezone)
    }
  }, [currentUser])

  const updatePreferencesMutation = useMutation({
    mutationFn: (data: UserPreferencesUpdate) => authAPI.updatePreferences(data),
    onSuccess: () => {
      toast({
        title: 'Preferences updated',
        description: 'Your preferences have been successfully saved.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Update failed',
        description: error.response?.data?.detail || 'Failed to update preferences',
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    },
  })

  const handleSavePreferences = () => {
    const data: UserPreferencesUpdate = {
      theme,
      language,
      currency,
      date_format: dateFormat,
      timezone,
    }

    updatePreferencesMutation.mutate(data)
  }

  return (
    <VStack spacing={6} align="stretch">
      <Card>
        <CardHeader>
          <Heading size="md">Appearance</Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel>Theme</FormLabel>
              <Select value={theme} onChange={(e) => setTheme(e.target.value as 'light' | 'dark' | 'system')}>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="system">System</option>
              </Select>
              <Text fontSize="sm" color="gray.500" mt={1}>
                Choose your preferred color theme
              </Text>
            </FormControl>
          </VStack>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <Heading size="md">Localization</Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel>Language</FormLabel>
              <LanguageSwitcher variant="buttons" size="md" />
              <Text fontSize="sm" color="gray.500" mt={2}>
                Choose your preferred language for the application
              </Text>
            </FormControl>

            <FormControl>
              <FormLabel>Currency</FormLabel>
              <Select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                <option value="USD">USD - US Dollar</option>
                <option value="EUR">EUR - Euro</option>
                <option value="GBP">GBP - British Pound</option>
                <option value="JPY">JPY - Japanese Yen</option>
                <option value="CAD">CAD - Canadian Dollar</option>
                <option value="AUD">AUD - Australian Dollar</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Date Format</FormLabel>
              <Select value={dateFormat} onChange={(e) => setDateFormat(e.target.value)}>
                <option value="MM/DD/YYYY">MM/DD/YYYY (US)</option>
                <option value="DD/MM/YYYY">DD/MM/YYYY (European)</option>
                <option value="YYYY-MM-DD">YYYY-MM-DD (ISO)</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Timezone</FormLabel>
              <Input
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="e.g., America/New_York"
              />
              <Text fontSize="sm" color="gray.500" mt={1}>
                IANA timezone identifier (e.g., America/New_York, Europe/Paris)
              </Text>
            </FormControl>
          </VStack>
        </CardBody>
      </Card>

      <Button
        colorScheme="blue"
        size={{ base: 'md', md: 'md' }}
        width={{ base: 'full', md: 'auto' }}
        onClick={handleSavePreferences}
        isLoading={updatePreferencesMutation.isPending}
      >
        Save Preferences
      </Button>
    </VStack>
  )
}
