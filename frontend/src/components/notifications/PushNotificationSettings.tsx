import { useState, useEffect } from 'react'
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Heading,
  VStack,
  Text,
  Switch,
  FormControl,
  FormLabel,
  useToast,
  Alert,
  AlertIcon,
  AlertDescription,
} from '@chakra-ui/react'
import apiClient from '../../api/client'

interface PushSubscription {
  endpoint: string
  keys: {
    p256dh: string
    auth: string
  }
}

export const PushNotificationSettings = () => {
  const [isSupported, setIsSupported] = useState(false)
  const [isSubscribed, setIsSubscribed] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [permission, setPermission] = useState<NotificationPermission>('default')
  const [vapidPublicKey, setVapidPublicKey] = useState<string>('')
  const toast = useToast()

  useEffect(() => {
    // Check if push notifications are supported
    const supported = 'serviceWorker' in navigator && 'PushManager' in window
    setIsSupported(supported)

    if (supported) {
      setPermission(Notification.permission)
      checkSubscription()
      fetchVapidPublicKey()
    }
  }, [])

  const fetchVapidPublicKey = async () => {
    try {
      const response = await apiClient.get('/push/vapid-public-key')
      setVapidPublicKey(response.data.publicKey)
    } catch (error) {
      console.error('Error fetching VAPID public key:', error)
      toast({
        title: 'Configuration Error',
        description: 'Failed to fetch push notification configuration',
        status: 'error',
        duration: 5000,
      })
    }
  }

  const checkSubscription = async () => {
    try {
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()
      setIsSubscribed(!!subscription)
    } catch (error) {
      console.error('Error checking subscription:', error)
    }
  }

  const urlBase64ToUint8Array = (base64String: string) => {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')

    const rawData = window.atob(base64)
    const outputArray = new Uint8Array(rawData.length)

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i)
    }
    return outputArray
  }

  const subscribeToPush = async () => {
    if (!isSupported) {
      toast({
        title: 'Not Supported',
        description: 'Push notifications are not supported in your browser',
        status: 'error',
        duration: 5000,
      })
      return
    }

    if (!vapidPublicKey) {
      toast({
        title: 'Configuration Error',
        description: 'Push notification configuration not available',
        status: 'error',
        duration: 5000,
      })
      return
    }

    setIsLoading(true)

    try {
      // Request notification permission
      const permissionResult = await Notification.requestPermission()
      setPermission(permissionResult)

      if (permissionResult !== 'granted') {
        toast({
          title: 'Permission Denied',
          description: 'Please enable notifications in your browser settings',
          status: 'warning',
          duration: 5000,
        })
        setIsLoading(false)
        return
      }

      // Get service worker registration
      const registration = await navigator.serviceWorker.ready

      // Subscribe to push notifications
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      })

      // Prepare subscription data for backend
      const subscriptionData: PushSubscription = {
        endpoint: subscription.endpoint,
        keys: {
          p256dh: btoa(
            String.fromCharCode(...new Uint8Array(subscription.getKey('p256dh')!))
          ),
          auth: btoa(
            String.fromCharCode(...new Uint8Array(subscription.getKey('auth')!))
          ),
        },
      }

      // Send subscription to backend API
      await apiClient.post('/push/subscribe', subscriptionData)

      setIsSubscribed(true)
      toast({
        title: 'Subscribed',
        description: 'You will now receive push notifications',
        status: 'success',
        duration: 5000,
      })
    } catch (error) {
      console.error('Error subscribing to push:', error)
      toast({
        title: 'Subscription Failed',
        description: 'Failed to subscribe to push notifications',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const unsubscribeFromPush = async () => {
    setIsLoading(true)

    try {
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()

      if (subscription) {
        // Notify backend before unsubscribing
        try {
          await apiClient.delete('/push/unsubscribe', {
            params: { endpoint: subscription.endpoint }
          })
        } catch (backendError) {
          console.error('Error notifying backend:', backendError)
          // Continue with local unsubscribe even if backend fails
        }

        // Unsubscribe from browser
        await subscription.unsubscribe()

        setIsSubscribed(false)
        toast({
          title: 'Unsubscribed',
          description: 'You will no longer receive push notifications',
          status: 'info',
          duration: 5000,
        })
      }
    } catch (error) {
      console.error('Error unsubscribing from push:', error)
      toast({
        title: 'Unsubscribe Failed',
        description: 'Failed to unsubscribe from push notifications',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleToggle = async () => {
    if (isSubscribed) {
      await unsubscribeFromPush()
    } else {
      await subscribeToPush()
    }
  }

  if (!isSupported) {
    return (
      <Card>
        <CardBody>
          <Alert status="warning">
            <AlertIcon />
            <AlertDescription>
              Push notifications are not supported in your browser. Please try using Chrome, Firefox, or Safari.
            </AlertDescription>
          </Alert>
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <Heading size="md">Push Notifications</Heading>
      </CardHeader>
      <CardBody>
        <VStack align="stretch" spacing={4}>
          <Text color="text.subtle">
            Receive notifications for upcoming subscription renewals and important updates.
          </Text>

          {permission === 'denied' && (
            <Alert status="error">
              <AlertIcon />
              <AlertDescription>
                Notifications are blocked. Please enable them in your browser settings.
              </AlertDescription>
            </Alert>
          )}

          <FormControl display="flex" alignItems="center">
            <FormLabel htmlFor="push-notifications" mb="0">
              Enable Push Notifications
            </FormLabel>
            <Switch
              id="push-notifications"
              isChecked={isSubscribed}
              onChange={handleToggle}
              isDisabled={isLoading || permission === 'denied'}
              colorScheme="blue"
            />
          </FormControl>

          {!isSubscribed && permission === 'default' && (
            <Button
              onClick={subscribeToPush}
              isLoading={isLoading}
              colorScheme="blue"
              variant="outline"
            >
              Enable Notifications
            </Button>
          )}
        </VStack>
      </CardBody>
    </Card>
  )
}
