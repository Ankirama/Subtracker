import { useState } from 'react'
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Button,
  VStack,
  Radio,
  RadioGroup,
  Textarea,
  Text,
  Box,
  Alert,
  AlertIcon,
  useToast,
} from '@chakra-ui/react'
import { useMutation } from '@tanstack/react-query'
import { subscriptionsAPI } from '../../api/subscriptions'
import { Subscription } from '../../types'

interface SubscriptionFeedbackModalProps {
  isOpen: boolean
  onClose: () => void
  subscription: Subscription
  onFeedbackSubmitted: () => void
}

const FEEDBACK_OPTIONS = [
  { value: 'not_subscription', label: 'Not a subscription', description: 'This is not actually a subscription service' },
  { value: 'duplicate', label: 'Duplicate', description: 'This subscription already exists' },
  { value: 'wrong_amount', label: 'Wrong amount', description: 'The detected amount is incorrect' },
  { value: 'wrong_provider', label: 'Wrong provider', description: 'The service provider is incorrect' },
  { value: 'wrong_category', label: 'Wrong category', description: 'The category is misclassified' },
  { value: 'wrong_billing_cycle', label: 'Wrong billing cycle', description: 'The billing frequency is incorrect' },
  { value: 'other', label: 'Other', description: 'Different issue (please explain below)' },
]

export const SubscriptionFeedbackModal = ({
  isOpen,
  onClose,
  subscription,
  onFeedbackSubmitted,
}: SubscriptionFeedbackModalProps) => {
  const [feedbackType, setFeedbackType] = useState<string>('')
  const [feedbackText, setFeedbackText] = useState('')
  const toast = useToast()

  const feedbackMutation = useMutation({
    mutationFn: async () => {
      if (!feedbackType) {
        throw new Error('Please select a feedback type')
      }

      await subscriptionsAPI.submitFeedback({
        subscription_id: subscription.id,
        feedback_type: feedbackType as any,
        feedback_text: feedbackText || undefined,
      })
    },
    onSuccess: () => {
      toast({
        title: 'Thank you for your feedback!',
        description: 'This helps improve our AI detection accuracy.',
        status: 'success',
        duration: 3000,
      })
      onFeedbackSubmitted()
      handleClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to submit feedback',
        description: error.message || 'Please try again',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const handleClose = () => {
    setFeedbackType('')
    setFeedbackText('')
    onClose()
  }

  const handleSubmit = () => {
    feedbackMutation.mutate()
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="lg">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Why are you removing this subscription?</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack align="stretch" spacing={4}>
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <Text fontSize="sm">
                Your feedback helps us improve AI detection accuracy for future subscriptions.
              </Text>
            </Alert>

            <Box>
              <Text fontWeight="medium" mb={2}>
                Subscription: {subscription.provider}
              </Text>
              <Text fontSize="sm" color="text.subtle">
                Amount: €{subscription.amount || 'N/A'} • {subscription.billing_cycle}
              </Text>
            </Box>

            <Box>
              <Text fontWeight="medium" mb={3}>
                What's the issue?
              </Text>
              <RadioGroup value={feedbackType} onChange={setFeedbackType}>
                <VStack align="stretch" spacing={3}>
                  {FEEDBACK_OPTIONS.map((option) => (
                    <Box
                      key={option.value}
                      p={3}
                      borderWidth={1}
                      borderRadius="md"
                      borderColor={feedbackType === option.value ? 'blue.500' : 'gray.200'}
                      bg={feedbackType === option.value ? 'blue.50' : 'white'}
                      cursor="pointer"
                      onClick={() => setFeedbackType(option.value)}
                      _hover={{ borderColor: 'blue.300' }}
                    >
                      <Radio value={option.value} colorScheme="blue">
                        <VStack align="start" spacing={0} ml={2}>
                          <Text fontWeight="medium">{option.label}</Text>
                          <Text fontSize="sm" color="text.subtle">
                            {option.description}
                          </Text>
                        </VStack>
                      </Radio>
                    </Box>
                  ))}
                </VStack>
              </RadioGroup>
            </Box>

            <Box>
              <Text fontWeight="medium" mb={2}>
                Additional details (optional)
              </Text>
              <Textarea
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
                placeholder="Any additional information that might help us improve..."
                rows={3}
              />
            </Box>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={handleClose}>
            Cancel
          </Button>
          <Button
            colorScheme="blue"
            onClick={handleSubmit}
            isLoading={feedbackMutation.isPending}
            isDisabled={!feedbackType}
          >
            Submit & Delete
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}
