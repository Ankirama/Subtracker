import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Box,
  Card,
  CardBody,
  VStack,
  HStack,
  Button,
  IconButton,
  Text,
  Textarea,
  FormControl,
  FormLabel,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Checkbox,
  CheckboxGroup,
  Stack,
  Divider,
  useToast,
  Collapse,
  useDisclosure,
  Badge,
  useColorModeValue,
} from '@chakra-ui/react'
import { FiThumbsUp, FiThumbsDown, FiChevronDown, FiChevronUp } from 'react-icons/fi'
import { feedbackAPI } from '../../api/feedback'
import { FeedbackSubmission, FeedbackTypeEnum } from '../../types'

interface FeedbackWidgetProps {
  providerCancellationId: string
  providerName: string
}

const ISSUE_OPTIONS = [
  'incorrect_url',
  'missing_steps',
  'outdated_info',
  'requires_phone',
  'unclear_instructions',
  'difficult_to_follow',
]

export const FeedbackWidget = ({ providerCancellationId, providerName }: FeedbackWidgetProps) => {
  const { isOpen, onToggle } = useDisclosure()
  const [feedbackGiven, setFeedbackGiven] = useState(false)
  const [selectedIssues, setSelectedIssues] = useState<string[]>([])
  const [detailedForm, setDetailedForm] = useState({
    successfully_cancelled: null as boolean | null,
    time_taken_minutes: null as number | null,
    helpfulness_rating: null as number | null,
    accuracy_rating: null as number | null,
    comment: '',
  })

  const toast = useToast()
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const bgColor = useColorModeValue('white', 'gray.800')

  const quickFeedbackMutation = useMutation({
    mutationFn: (feedbackType: 'helpful' | 'not_helpful') =>
      feedbackAPI.submitQuickFeedback({
        provider_cancellation_id: providerCancellationId,
        feedback_type: feedbackType,
      }),
    onSuccess: () => {
      setFeedbackGiven(true)
      toast({
        title: 'Thank you for your feedback!',
        description: 'Your response helps us improve cancellation instructions.',
        status: 'success',
        duration: 3000,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to submit feedback',
        description: error?.response?.data?.detail || 'Please try again.',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const detailedFeedbackMutation = useMutation({
    mutationFn: (data: FeedbackSubmission) => feedbackAPI.submitFeedback(data),
    onSuccess: () => {
      setFeedbackGiven(true)
      toast({
        title: 'Detailed feedback submitted',
        description: 'Thank you for helping us improve!',
        status: 'success',
        duration: 3000,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to submit feedback',
        description: error?.response?.data?.detail || 'Please try again.',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const handleQuickFeedback = (isHelpful: boolean) => {
    quickFeedbackMutation.mutate(isHelpful ? 'helpful' : 'not_helpful')
  }

  const handleDetailedSubmit = () => {
    const feedbackType: FeedbackTypeEnum = detailedForm.successfully_cancelled
      ? 'worked'
      : detailedForm.successfully_cancelled === false
      ? 'failed'
      : selectedIssues.length > 0
      ? 'incomplete'
      : 'helpful'

    detailedFeedbackMutation.mutate({
      provider_cancellation_id: providerCancellationId,
      feedback_type: feedbackType,
      successfully_cancelled: detailedForm.successfully_cancelled,
      time_taken_minutes: detailedForm.time_taken_minutes,
      helpfulness_rating: detailedForm.helpfulness_rating,
      accuracy_rating: detailedForm.accuracy_rating,
      comment: detailedForm.comment || null,
      issues_encountered: selectedIssues.length > 0 ? selectedIssues : null,
      device_type: 'web',
    })
  }

  if (feedbackGiven) {
    return (
      <Card bg={bgColor} borderColor="green.500" borderWidth="2px">
        <CardBody>
          <HStack spacing={2}>
            <Badge colorScheme="green">Feedback Received</Badge>
            <Text color="text.subtle" fontSize="sm">
              Thank you for helping improve {providerName} cancellation instructions!
            </Text>
          </HStack>
        </CardBody>
      </Card>
    )
  }

  return (
    <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
      <CardBody>
        <VStack align="stretch" spacing={4}>
          <Box>
            <Text fontWeight="bold" mb={2}>
              Were these instructions helpful?
            </Text>
            <HStack spacing={4}>
              <Button
                leftIcon={<FiThumbsUp />}
                colorScheme="green"
                variant="outline"
                onClick={() => handleQuickFeedback(true)}
                isLoading={quickFeedbackMutation.isPending}
              >
                Yes, helpful
              </Button>
              <Button
                leftIcon={<FiThumbsDown />}
                colorScheme="red"
                variant="outline"
                onClick={() => handleQuickFeedback(false)}
                isLoading={quickFeedbackMutation.isPending}
              >
                Not helpful
              </Button>
            </HStack>
          </Box>

          <Divider />

          <Box>
            <Button
              size="sm"
              variant="ghost"
              rightIcon={isOpen ? <FiChevronUp /> : <FiChevronDown />}
              onClick={onToggle}
            >
              {isOpen ? 'Hide' : 'Show'} detailed feedback form
            </Button>

            <Collapse in={isOpen} animateOpacity>
              <VStack align="stretch" spacing={4} mt={4}>
                <FormControl>
                  <FormLabel>Did you successfully cancel?</FormLabel>
                  <HStack spacing={4}>
                    <Button
                      size="sm"
                      colorScheme={detailedForm.successfully_cancelled === true ? 'green' : 'gray'}
                      variant={detailedForm.successfully_cancelled === true ? 'solid' : 'outline'}
                      onClick={() =>
                        setDetailedForm({ ...detailedForm, successfully_cancelled: true })
                      }
                    >
                      Yes
                    </Button>
                    <Button
                      size="sm"
                      colorScheme={detailedForm.successfully_cancelled === false ? 'red' : 'gray'}
                      variant={detailedForm.successfully_cancelled === false ? 'solid' : 'outline'}
                      onClick={() =>
                        setDetailedForm({ ...detailedForm, successfully_cancelled: false })
                      }
                    >
                      No
                    </Button>
                    <Button
                      size="sm"
                      colorScheme={detailedForm.successfully_cancelled === null ? 'blue' : 'gray'}
                      variant={detailedForm.successfully_cancelled === null ? 'solid' : 'outline'}
                      onClick={() =>
                        setDetailedForm({ ...detailedForm, successfully_cancelled: null })
                      }
                    >
                      Not yet tried
                    </Button>
                  </HStack>
                </FormControl>

                <FormControl>
                  <FormLabel>How long did it take? (minutes)</FormLabel>
                  <NumberInput
                    min={1}
                    max={120}
                    value={detailedForm.time_taken_minutes || ''}
                    onChange={(_, val) => setDetailedForm({ ...detailedForm, time_taken_minutes: val })}
                  >
                    <NumberInputField placeholder="e.g., 15" />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                </FormControl>

                <FormControl>
                  <FormLabel>Helpfulness rating (1-5)</FormLabel>
                  <HStack spacing={2}>
                    {[1, 2, 3, 4, 5].map((rating) => (
                      <Button
                        key={rating}
                        size="sm"
                        colorScheme={detailedForm.helpfulness_rating === rating ? 'blue' : 'gray'}
                        variant={detailedForm.helpfulness_rating === rating ? 'solid' : 'outline'}
                        onClick={() =>
                          setDetailedForm({ ...detailedForm, helpfulness_rating: rating })
                        }
                      >
                        {rating}
                      </Button>
                    ))}
                  </HStack>
                </FormControl>

                <FormControl>
                  <FormLabel>Accuracy rating (1-5)</FormLabel>
                  <HStack spacing={2}>
                    {[1, 2, 3, 4, 5].map((rating) => (
                      <Button
                        key={rating}
                        size="sm"
                        colorScheme={detailedForm.accuracy_rating === rating ? 'blue' : 'gray'}
                        variant={detailedForm.accuracy_rating === rating ? 'solid' : 'outline'}
                        onClick={() =>
                          setDetailedForm({ ...detailedForm, accuracy_rating: rating })
                        }
                      >
                        {rating}
                      </Button>
                    ))}
                  </HStack>
                </FormControl>

                <FormControl>
                  <FormLabel>Issues encountered (select all that apply)</FormLabel>
                  <CheckboxGroup value={selectedIssues} onChange={(values) => setSelectedIssues(values as string[])}>
                    <Stack spacing={2}>
                      {ISSUE_OPTIONS.map((issue) => (
                        <Checkbox key={issue} value={issue}>
                          {issue.replace(/_/g, ' ')}
                        </Checkbox>
                      ))}
                    </Stack>
                  </CheckboxGroup>
                </FormControl>

                <FormControl>
                  <FormLabel>Additional comments</FormLabel>
                  <Textarea
                    value={detailedForm.comment}
                    onChange={(e) => setDetailedForm({ ...detailedForm, comment: e.target.value })}
                    placeholder="Any other feedback or suggestions..."
                    rows={3}
                  />
                </FormControl>

                <Button
                  colorScheme="blue"
                  onClick={handleDetailedSubmit}
                  isLoading={detailedFeedbackMutation.isPending}
                >
                  Submit Detailed Feedback
                </Button>
              </VStack>
            </Collapse>
          </Box>
        </VStack>
      </CardBody>
    </Card>
  )
}
