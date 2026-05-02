import { useState, useEffect } from 'react'
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Switch,
  FormControl,
  FormLabel,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Select,
  Card,
  CardBody,
  CardHeader,
  useToast,
  Spinner,
  Center,
  Divider,
  Badge,
  Icon,
  useColorModeValue,
} from '@chakra-ui/react'
import {
  notificationsApi,
  NotificationPreference,
} from '../../api/notifications'
import { FiBell, FiMail, FiCheck } from 'react-icons/fi'
import { PushNotificationSettings } from './PushNotificationSettings'

const NOTIFICATION_TYPES = [
  {
    type: 'TRIAL_ENDING',
    label: 'Trial Ending Reminders',
    description: 'Get notified before free trials end to avoid charges',
    icon: '⚠️',
    hasSettings: false,
  },
  {
    type: 'RENEWAL_REMINDER',
    label: 'Renewal Reminders',
    description: 'Get notified before your subscriptions renew',
    icon: '🔔',
    hasSettings: true,
  },
  {
    type: 'WEEKLY_SUMMARY',
    label: 'Weekly Summary',
    description: 'Weekly overview of your subscription spending',
    icon: '📊',
    hasSettings: true,
  },
  {
    type: 'MONTHLY_SUMMARY',
    label: 'Monthly Summary',
    description: 'Monthly spending report and insights',
    icon: '📈',
    hasSettings: true,
  },
  {
    type: 'INACTIVE_SUBSCRIPTION',
    label: 'Inactive Subscriptions',
    description: 'Alert when subscriptions appear inactive',
    icon: '⏸️',
    hasSettings: false,
  },
  {
    type: 'PRICE_CHANGE',
    label: 'Price Changes',
    description: 'Notify when subscription prices change',
    icon: '💰',
    hasSettings: false,
  },
  {
    type: 'SYSTEM_ANNOUNCEMENT',
    label: 'System Announcements',
    description: 'Important updates and announcements',
    icon: '📢',
    hasSettings: false,
  },
]

const DAYS_OF_WEEK = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
]

export const NotificationSettingsPage = () => {
  const [preferences, setPreferences] = useState<Record<string, NotificationPreference>>({})
  const [isLoading, setIsLoading] = useState(true)
  const toast = useToast()

  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  useEffect(() => {
    fetchPreferences()
  }, [])

  const fetchPreferences = async () => {
    setIsLoading(true)
    try {
      const data = await notificationsApi.getPreferences()
      const prefsMap = data.preferences.reduce((acc, pref) => {
        acc[pref.notification_type] = pref
        return acc
      }, {} as Record<string, NotificationPreference>)
      setPreferences(prefsMap)
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load notification preferences',
        status: 'error',
        duration: 3000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const updatePreference = async (
    notificationType: string,
    updates: Partial<NotificationPreference>
  ) => {
    try {
      const updatedPref = await notificationsApi.updatePreference(notificationType, updates)
      setPreferences((prev) => ({
        ...prev,
        [notificationType]: updatedPref,
      }))
      toast({
        title: 'Success',
        description: 'Preference updated',
        status: 'success',
        duration: 2000,
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to update preference',
        status: 'error',
        duration: 3000,
      })
    }
  }

  if (isLoading) {
    return (
      <Center h="100vh">
        <Spinner size="xl" />
      </Center>
    )
  }

  return (
    <Container maxW="container.lg" py={8}>
      <VStack align="stretch" spacing={6}>
        <Box>
          <Heading size="lg" mb={2}>
            Notification Settings
          </Heading>
          <Text color="text.subtle">
            Customize how and when you want to receive notifications
          </Text>
        </Box>

        {/* Push Notifications Section */}
        <PushNotificationSettings />

        <Divider />

        <Box>
          <Heading size="md" mb={2}>
            Notification Preferences
          </Heading>
          <Text color="text.subtle" fontSize="sm">
            Configure email and in-app notification preferences
          </Text>
        </Box>

        <VStack align="stretch" spacing={4}>
          {NOTIFICATION_TYPES.map((notifType) => {
            const pref = preferences[notifType.type]
            if (!pref) return null

            return (
              <Card key={notifType.type} bg={cardBg} borderColor={borderColor}>
                <CardHeader pb={2}>
                  <HStack justify="space-between">
                    <HStack spacing={3}>
                      <Text fontSize="2xl">{notifType.icon}</Text>
                      <Box>
                        <Text fontWeight="bold">{notifType.label}</Text>
                        <Text fontSize="sm" color="text.subtle">
                          {notifType.description}
                        </Text>
                      </Box>
                    </HStack>
                    <FormControl display="flex" alignItems="center" w="auto">
                      <Switch
                        id={`enabled-${notifType.type}`}
                        colorScheme="blue"
                        isChecked={pref.enabled}
                        onChange={(e) =>
                          updatePreference(notifType.type, { enabled: e.target.checked })
                        }
                      />
                    </FormControl>
                  </HStack>
                </CardHeader>

                {pref.enabled && (
                  <CardBody pt={0}>
                    <VStack align="stretch" spacing={4}>
                      <Divider />

                      {/* In-app and Email toggles */}
                      <HStack spacing={6}>
                        <FormControl display="flex" alignItems="center">
                          <Icon as={FiBell} mr={2} />
                          <FormLabel htmlFor={`in-app-${notifType.type}`} mb={0} mr={2}>
                            In-app
                          </FormLabel>
                          <Switch
                            id={`in-app-${notifType.type}`}
                            colorScheme="blue"
                            size="sm"
                            isChecked={pref.in_app_enabled}
                            onChange={(e) =>
                              updatePreference(notifType.type, {
                                in_app_enabled: e.target.checked,
                              })
                            }
                          />
                        </FormControl>

                        <FormControl display="flex" alignItems="center">
                          <Icon as={FiMail} mr={2} />
                          <FormLabel htmlFor={`email-${notifType.type}`} mb={0} mr={2}>
                            Email
                          </FormLabel>
                          <Switch
                            id={`email-${notifType.type}`}
                            colorScheme="blue"
                            size="sm"
                            isChecked={pref.email_enabled}
                            onChange={(e) =>
                              updatePreference(notifType.type, {
                                email_enabled: e.target.checked,
                              })
                            }
                          />
                        </FormControl>
                      </HStack>

                      {/* Type-specific settings */}
                      {notifType.type === 'RENEWAL_REMINDER' && (
                        <FormControl>
                          <FormLabel fontSize="sm">Days before renewal to notify</FormLabel>
                          <NumberInput
                            min={0}
                            max={30}
                            value={pref.days_before_renewal || 3}
                            onChange={(valueString) => {
                              const value = parseInt(valueString) || 3
                              updatePreference(notifType.type, { days_before_renewal: value })
                            }}
                          >
                            <NumberInputField />
                            <NumberInputStepper>
                              <NumberIncrementStepper />
                              <NumberDecrementStepper />
                            </NumberInputStepper>
                          </NumberInput>
                          <Text fontSize="xs" color="gray.500" mt={1}>
                            Receive reminder {pref.days_before_renewal || 3} days before renewal
                          </Text>
                        </FormControl>
                      )}

                      {notifType.type === 'WEEKLY_SUMMARY' && (
                        <FormControl>
                          <FormLabel fontSize="sm">Day to send summary</FormLabel>
                          <Select
                            value={pref.summary_day_of_week ?? 0}
                            onChange={(e) =>
                              updatePreference(notifType.type, {
                                summary_day_of_week: parseInt(e.target.value),
                              })
                            }
                          >
                            {DAYS_OF_WEEK.map((day) => (
                              <option key={day.value} value={day.value}>
                                {day.label}
                              </option>
                            ))}
                          </Select>
                          <Text fontSize="xs" color="gray.500" mt={1}>
                            Weekly summary sent every{' '}
                            {DAYS_OF_WEEK.find((d) => d.value === (pref.summary_day_of_week ?? 0))
                              ?.label || 'Monday'}
                          </Text>
                        </FormControl>
                      )}

                      {notifType.type === 'MONTHLY_SUMMARY' && (
                        <FormControl>
                          <FormLabel fontSize="sm">Day of month to send summary</FormLabel>
                          <NumberInput
                            min={1}
                            max={31}
                            value={pref.summary_day_of_month || 1}
                            onChange={(valueString) => {
                              const value = parseInt(valueString) || 1
                              updatePreference(notifType.type, { summary_day_of_month: value })
                            }}
                          >
                            <NumberInputField />
                            <NumberInputStepper>
                              <NumberIncrementStepper />
                              <NumberDecrementStepper />
                            </NumberInputStepper>
                          </NumberInput>
                          <Text fontSize="xs" color="gray.500" mt={1}>
                            Monthly summary sent on the {pref.summary_day_of_month || 1}
                            {['st', 'nd', 'rd'][
                              ((pref.summary_day_of_month || 1) % 10) - 1
                            ] || 'th'}{' '}
                            of each month
                          </Text>
                        </FormControl>
                      )}
                    </VStack>
                  </CardBody>
                )}
              </Card>
            )
          })}
        </VStack>

        <Card bg={cardBg} borderColor={borderColor}>
          <CardBody>
            <HStack spacing={2}>
              <Icon as={FiCheck} color="green.500" />
              <Text fontSize="sm" color="text.subtle">
                Your preferences are saved automatically
              </Text>
            </HStack>
          </CardBody>
        </Card>
      </VStack>
    </Container>
  )
}
