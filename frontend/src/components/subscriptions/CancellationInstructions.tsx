import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Box,
  Card,
  CardHeader,
  CardBody,
  Heading,
  VStack,
  HStack,
  Text,
  Button,
  Badge,
  Icon,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Link,
  OrderedList,
  ListItem,
  UnorderedList,
  Divider,
  useToast,
} from '@chakra-ui/react'
import {
  FiExternalLink,
  FiClock,
  FiAlertTriangle,
  FiPhone,
  FiMessageSquare,
  FiPauseCircle,
  FiRefreshCw,
} from 'react-icons/fi'
import { cancellationAPI } from '../../api/cancellation'
import { ProviderCancellationInfo, DifficultyRating } from '../../types'
import { FeedbackWidget } from '../feedback/FeedbackWidget'

interface CancellationInstructionsProps {
  providerName: string
  subscriptionId: string
  existingInfo?: ProviderCancellationInfo | null
}

export const CancellationInstructions = ({
  providerName,
  subscriptionId,
  existingInfo,
}: CancellationInstructionsProps) => {
  const [cancellationInfo, setCancellationInfo] = useState<ProviderCancellationInfo | null>(
    existingInfo || null
  )
  const toast = useToast()

  const researchMutation = useMutation({
    mutationFn: () =>
      cancellationAPI.researchProvider({
        provider_name: providerName,
        force_refresh: false,
      }),
    onSuccess: async (data) => {
      // After research completes, fetch the saved provider info with ID
      try {
        const providerInfo = await cancellationAPI.getProviderInfo(data.provider_name)
        setCancellationInfo(providerInfo)
      } catch (error) {
        // Fallback to manual construction if fetch fails
        setCancellationInfo({
          id: '',
          provider_name: data.provider_name,
          cancellation_url: data.cancellation_url,
          difficulty_rating: data.difficulty_rating,
          instructions: data.instructions,
          instructions_source: 'ai',
          requires_phone_call: data.requires_phone_call,
          requires_chat: data.requires_chat,
          allows_pause: data.allows_pause,
          pause_instructions: data.pause_instructions,
          additional_notes: data.additional_notes,
          estimated_time_minutes: data.estimated_time_minutes,
          cancellation_gotchas: data.cancellation_gotchas,
          ai_confidence_score: data.ai_confidence_score,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          is_verified: false,
          needs_reverification: false,
          is_ai_generated: true,
        })
      }
      toast({
        title: 'Instructions Generated',
        description: 'AI has researched cancellation instructions for this provider.',
        status: 'success',
        duration: 3000,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Research Failed',
        description: error?.response?.data?.detail || 'Failed to research cancellation instructions.',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const getDifficultyColor = (difficulty: DifficultyRating): string => {
    switch (difficulty) {
      case 'easy':
        return 'green'
      case 'medium':
        return 'yellow'
      case 'hard':
        return 'red'
      default:
        return 'gray'
    }
  }

  const getDifficultyEmoji = (difficulty: DifficultyRating): string => {
    switch (difficulty) {
      case 'easy':
        return '✅'
      case 'medium':
        return '⚠️'
      case 'hard':
        return '🔴'
      default:
        return '❓'
    }
  }

  if (!cancellationInfo) {
    return (
      <Card>
        <CardHeader>
          <Heading size="md">Cancellation Instructions</Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <Text color="text.subtle">
              No cancellation instructions available yet. Click below to have our AI research the
              cancellation process for {providerName}.
            </Text>
            <Button
              colorScheme="blue"
              leftIcon={<Icon as={FiRefreshCw} />}
              onClick={() => researchMutation.mutate()}
              isLoading={researchMutation.isPending}
              loadingText="Researching..."
            >
              Research Cancellation Instructions
            </Button>
          </VStack>
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={1}>
            <Heading size="md">Cancellation Instructions</Heading>
            {cancellationInfo.is_ai_generated && (
              <Badge colorScheme="purple">AI-Generated</Badge>
            )}
          </VStack>
          <Button
            size="sm"
            variant="outline"
            leftIcon={<Icon as={FiRefreshCw} />}
            onClick={() => researchMutation.mutate()}
            isLoading={researchMutation.isPending}
          >
            Refresh
          </Button>
        </HStack>
      </CardHeader>
      <CardBody>
        <VStack spacing={6} align="stretch">
          {/* Difficulty & Time Estimate */}
          <HStack spacing={6} wrap="wrap">
            <HStack>
              <Text fontWeight="semibold">Difficulty:</Text>
              <Badge
                colorScheme={getDifficultyColor(cancellationInfo.difficulty_rating)}
                fontSize="md"
                px={3}
                py={1}
              >
                {getDifficultyEmoji(cancellationInfo.difficulty_rating)}{' '}
                {cancellationInfo.difficulty_rating.toUpperCase()}
              </Badge>
            </HStack>

            {cancellationInfo.estimated_time_minutes && (
              <HStack>
                <Icon as={FiClock} color="gray.500" />
                <Text fontWeight="semibold">Estimated Time:</Text>
                <Text>{cancellationInfo.estimated_time_minutes} minutes</Text>
              </HStack>
            )}

            {cancellationInfo.ai_confidence_score && (
              <HStack>
                <Text fontWeight="semibold">Confidence:</Text>
                <Text>{(cancellationInfo.ai_confidence_score * 100).toFixed(0)}%</Text>
              </HStack>
            )}
          </HStack>

          <Divider />

          {/* Cancellation URL */}
          {cancellationInfo.cancellation_url && (
            <Box>
              <Text fontWeight="semibold" mb={2}>
                Cancellation Link:
              </Text>
              <Link
                href={cancellationInfo.cancellation_url}
                isExternal
                color="blue.600"
                display="flex"
                alignItems="center"
                gap={2}
              >
                {cancellationInfo.cancellation_url}
                <Icon as={FiExternalLink} />
              </Link>
            </Box>
          )}

          {/* Requirements Badges */}
          <HStack spacing={3} wrap="wrap">
            {cancellationInfo.requires_phone_call && (
              <Badge colorScheme="orange" fontSize="sm" px={3} py={1}>
                <HStack spacing={1}>
                  <Icon as={FiPhone} />
                  <Text>Phone Call Required</Text>
                </HStack>
              </Badge>
            )}
            {cancellationInfo.requires_chat && (
              <Badge colorScheme="blue" fontSize="sm" px={3} py={1}>
                <HStack spacing={1}>
                  <Icon as={FiMessageSquare} />
                  <Text>Live Chat Required</Text>
                </HStack>
              </Badge>
            )}
            {cancellationInfo.allows_pause && (
              <Badge colorScheme="green" fontSize="sm" px={3} py={1}>
                <HStack spacing={1}>
                  <Icon as={FiPauseCircle} />
                  <Text>Pause Available</Text>
                </HStack>
              </Badge>
            )}
          </HStack>

          <Divider />

          {/* Step-by-Step Instructions */}
          {cancellationInfo.instructions && cancellationInfo.instructions.length > 0 && (
            <Box>
              <Text fontWeight="semibold" mb={3} fontSize="lg">
                How to Cancel:
              </Text>
              <OrderedList spacing={2} pl={4}>
                {cancellationInfo.instructions.map((instruction, index) => (
                  <ListItem key={index}>
                    <Text>{instruction}</Text>
                  </ListItem>
                ))}
              </OrderedList>
            </Box>
          )}

          {/* Pause Instructions */}
          {cancellationInfo.allows_pause &&
            cancellationInfo.pause_instructions &&
            cancellationInfo.pause_instructions.length > 0 && (
              <>
                <Divider />
                <Box>
                  <HStack mb={3}>
                    <Icon as={FiPauseCircle} color="green.500" />
                    <Text fontWeight="semibold" fontSize="lg">
                      How to Pause (Alternative):
                    </Text>
                  </HStack>
                  <OrderedList spacing={2} pl={4}>
                    {cancellationInfo.pause_instructions.map((instruction, index) => (
                      <ListItem key={index}>
                        <Text>{instruction}</Text>
                      </ListItem>
                    ))}
                  </OrderedList>
                </Box>
              </>
            )}

          {/* Gotchas / Warnings */}
          {cancellationInfo.cancellation_gotchas &&
            cancellationInfo.cancellation_gotchas.length > 0 && (
              <>
                <Divider />
                <Alert status="warning" borderRadius="md">
                  <AlertIcon as={FiAlertTriangle} />
                  <Box>
                    <AlertTitle>Important Gotchas</AlertTitle>
                    <AlertDescription>
                      <UnorderedList mt={2} spacing={1}>
                        {cancellationInfo.cancellation_gotchas.map((gotcha, index) => (
                          <ListItem key={index}>{gotcha}</ListItem>
                        ))}
                      </UnorderedList>
                    </AlertDescription>
                  </Box>
                </Alert>
              </>
            )}

          {/* Additional Notes */}
          {cancellationInfo.additional_notes && (
            <>
              <Divider />
              <Box p={4} bg="bg.subtle" borderRadius="md">
                <Text fontWeight="semibold" mb={2}>
                  Additional Notes:
                </Text>
                <Text color="gray.700">{cancellationInfo.additional_notes}</Text>
              </Box>
            </>
          )}

          {/* Verification Status */}
          {!cancellationInfo.is_verified && (
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <Text fontSize="sm">
                These instructions have not been verified. If you find any inaccuracies, please let
                us know.
              </Text>
            </Alert>
          )}

          {/* Feedback Widget */}
          {cancellationInfo.id && (
            <>
              <Divider />
              <FeedbackWidget
                providerCancellationId={cancellationInfo.id}
                providerName={providerName}
              />
            </>
          )}
        </VStack>
      </CardBody>
    </Card>
  )
}
