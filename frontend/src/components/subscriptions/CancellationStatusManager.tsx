import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
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
  FormControl,
  FormLabel,
  Select,
  Textarea,
  useToast,
  Divider,
} from '@chakra-ui/react'
import { FiCheckCircle, FiClock, FiPauseCircle, FiXCircle, FiSave } from 'react-icons/fi'
import { cancellationAPI } from '../../api/cancellation'
import { CancellationStatus, SubscriptionCancellationInfo } from '../../types'

interface CancellationStatusManagerProps {
  subscriptionId: string
  cancellationInfo?: SubscriptionCancellationInfo | null
}

export const CancellationStatusManager = ({
  subscriptionId,
  cancellationInfo,
}: CancellationStatusManagerProps) => {
  const [selectedStatus, setSelectedStatus] = useState<CancellationStatus>(
    cancellationInfo?.cancellation_status || 'active'
  )
  const [notes, setNotes] = useState<string>(cancellationInfo?.cancellation_notes || '')
  const [hasChanges, setHasChanges] = useState(false)

  const toast = useToast()
  const queryClient = useQueryClient()

  const updateStatusMutation = useMutation({
    mutationFn: () =>
      cancellationAPI.updateCancellationStatus(subscriptionId, {
        cancellation_status: selectedStatus,
        cancellation_notes: notes || null,
      }),
    onSuccess: () => {
      setHasChanges(false)
      queryClient.invalidateQueries({ queryKey: ['subscription', subscriptionId] })
      queryClient.invalidateQueries({ queryKey: ['cancellation', subscriptionId] })
      toast({
        title: 'Status Updated',
        description: 'Cancellation status has been updated successfully.',
        status: 'success',
        duration: 3000,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Update Failed',
        description: error?.response?.data?.detail || 'Failed to update cancellation status.',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const handleStatusChange = (status: CancellationStatus) => {
    setSelectedStatus(status)
    setHasChanges(true)
  }

  const handleNotesChange = (value: string) => {
    setNotes(value)
    setHasChanges(true)
  }

  const handleSave = () => {
    updateStatusMutation.mutate()
  }

  const getStatusIcon = (status: CancellationStatus) => {
    switch (status) {
      case 'active':
        return FiCheckCircle
      case 'pending_cancellation':
        return FiClock
      case 'paused':
        return FiPauseCircle
      case 'cancelled':
        return FiXCircle
      default:
        return FiCheckCircle
    }
  }

  const getStatusColor = (status: CancellationStatus): string => {
    switch (status) {
      case 'active':
        return 'green'
      case 'pending_cancellation':
        return 'yellow'
      case 'paused':
        return 'blue'
      case 'cancelled':
        return 'red'
      default:
        return 'gray'
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <Card>
      <CardHeader>
        <Heading size="md">Cancellation Status</Heading>
      </CardHeader>
      <CardBody>
        <VStack spacing={4} align="stretch">
          {/* Current Status Display */}
          <HStack>
            <Text fontWeight="semibold">Current Status:</Text>
            <Badge
              colorScheme={getStatusColor(cancellationInfo?.cancellation_status || 'active')}
              fontSize="md"
              px={3}
              py={1}
            >
              <HStack spacing={1}>
                <Icon as={getStatusIcon(cancellationInfo?.cancellation_status || 'active')} />
                <Text>{(cancellationInfo?.cancellation_status || 'active').replace('_', ' ').toUpperCase()}</Text>
              </HStack>
            </Badge>
          </HStack>

          {/* Status Timeline */}
          {(cancellationInfo?.cancellation_requested_at ||
            cancellationInfo?.cancellation_confirmed_at) && (
            <Box p={3} bg="bg.subtle" borderRadius="md">
              <VStack align="stretch" spacing={2} fontSize="sm">
                {cancellationInfo.cancellation_requested_at && (
                  <HStack>
                    <Icon as={FiClock} color="gray.500" />
                    <Text fontWeight="semibold">Requested:</Text>
                    <Text>{formatDate(cancellationInfo.cancellation_requested_at)}</Text>
                  </HStack>
                )}
                {cancellationInfo.cancellation_confirmed_at && (
                  <HStack>
                    <Icon as={FiCheckCircle} color="green.500" />
                    <Text fontWeight="semibold">Confirmed:</Text>
                    <Text>{formatDate(cancellationInfo.cancellation_confirmed_at)}</Text>
                  </HStack>
                )}
              </VStack>
            </Box>
          )}

          <Divider />

          {/* Status Update Form */}
          <FormControl>
            <FormLabel>Update Status</FormLabel>
            <Select
              value={selectedStatus}
              onChange={(e) => handleStatusChange(e.target.value as CancellationStatus)}
              size="md"
            >
              <option value="active">Active - Subscription is running</option>
              <option value="pending_cancellation">
                Pending Cancellation - Cancellation requested but not confirmed
              </option>
              <option value="paused">Paused - Temporarily suspended</option>
              <option value="cancelled">Cancelled - Successfully cancelled</option>
            </Select>
          </FormControl>

          <FormControl>
            <FormLabel>Notes</FormLabel>
            <Textarea
              value={notes}
              onChange={(e) => handleNotesChange(e.target.value)}
              placeholder="Add any notes about the cancellation process, confirmation numbers, or other details..."
              rows={4}
              resize="vertical"
            />
          </FormControl>

          {/* Save Button */}
          <Button
            colorScheme="blue"
            leftIcon={<Icon as={FiSave} />}
            onClick={handleSave}
            isLoading={updateStatusMutation.isPending}
            isDisabled={!hasChanges}
            loadingText="Saving..."
          >
            Save Changes
          </Button>

          {/* Status Descriptions */}
          <Box p={4} bg="bg.accent.blue" borderRadius="md" fontSize="sm">
            <Text fontWeight="semibold" mb={2}>
              Status Guide:
            </Text>
            <VStack align="stretch" spacing={1} color="gray.700">
              <Text>
                <strong>Active:</strong> Subscription is currently running and billing normally
              </Text>
              <Text>
                <strong>Pending Cancellation:</strong> You've initiated cancellation but haven't
                received confirmation yet
              </Text>
              <Text>
                <strong>Paused:</strong> Subscription is temporarily suspended (if provider allows
                pausing)
              </Text>
              <Text>
                <strong>Cancelled:</strong> Subscription has been successfully cancelled and will not
                renew
              </Text>
            </VStack>
          </Box>
        </VStack>
      </CardBody>
    </Card>
  )
}
