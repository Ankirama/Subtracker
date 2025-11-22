import { useState } from 'react'
import {
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Box,
  Button,
  HStack,
  Text,
  useColorModeValue,
  useToast,
  CloseButton,
} from '@chakra-ui/react'
import { Subscription } from '../../types'
import { subscriptionsAPI } from '../../api/subscriptions'
import { formatDistanceToNow } from '../../utils/timeFormat'

interface CancellationSuggestionBannerProps {
  subscription: Subscription
  onUpdate: () => void
}

export const CancellationSuggestionBanner = ({
  subscription,
  onUpdate,
}: CancellationSuggestionBannerProps) => {
  const [isAccepting, setIsAccepting] = useState(false)
  const [isDismissing, setIsDismissing] = useState(false)
  const [isVisible, setIsVisible] = useState(true)
  const toast = useToast()

  const bgColor = useColorModeValue('orange.50', 'gray.700')
  const borderColor = useColorModeValue('orange.400', 'orange.600')

  // Don't show banner if no suggestion exists or if it's been dismissed
  if (
    !subscription.suggested_cancellation_status ||
    !subscription.cancellation_suggestion_reason ||
    !isVisible
  ) {
    return null
  }

  const handleAccept = async () => {
    setIsAccepting(true)
    try {
      await subscriptionsAPI.acceptCancellationSuggestion(subscription.id)
      toast({
        title: 'Suggestion Accepted',
        description: 'The subscription has been marked as cancelled.',
        status: 'success',
        duration: 3000,
      })
      onUpdate() // Refresh the subscription data
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to accept cancellation suggestion.',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsAccepting(false)
    }
  }

  const handleDismiss = async () => {
    setIsDismissing(true)
    try {
      await subscriptionsAPI.dismissCancellationSuggestion(subscription.id)
      toast({
        title: 'Suggestion Dismissed',
        description: 'The cancellation suggestion has been removed.',
        status: 'info',
        duration: 3000,
      })
      setIsVisible(false)
      onUpdate() // Refresh the subscription data
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to dismiss cancellation suggestion.',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsDismissing(false)
    }
  }

  const suggestionAge = subscription.cancellation_suggestion_created_at
    ? formatDistanceToNow(new Date(subscription.cancellation_suggestion_created_at))
    : 'recently'

  return (
    <Alert
      status="warning"
      variant="left-accent"
      bg={bgColor}
      borderColor={borderColor}
      borderWidth="1px"
      borderRadius="md"
      mb={4}
    >
      <AlertIcon />
      <Box flex="1">
        <AlertTitle mb={1}>AI Detected Potential Cancellation</AlertTitle>
        <AlertDescription display="block">
          <Text mb={2}>{subscription.cancellation_suggestion_reason}</Text>
          <Text fontSize="sm" color="text.subtle" mb={3}>
            Detected {suggestionAge}
          </Text>
          <HStack spacing={3}>
            <Button
              colorScheme="orange"
              size="sm"
              onClick={handleAccept}
              isLoading={isAccepting}
              loadingText="Accepting..."
            >
              Accept & Mark as Cancelled
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDismiss}
              isLoading={isDismissing}
              loadingText="Dismissing..."
            >
              Dismiss Suggestion
            </Button>
          </HStack>
        </AlertDescription>
      </Box>
      <CloseButton
        alignSelf="flex-start"
        position="relative"
        right={-1}
        top={-1}
        onClick={handleDismiss}
        isDisabled={isDismissing}
      />
    </Alert>
  )
}
