import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@chakra-ui/react'

import { aiSandboxAPI } from '../api/aiSandbox'
import type { EmailDetailResponse } from '../types'

interface UseUncertainEmailsManagementOptions {
  onEmailDetailLoaded?: (email: EmailDetailResponse) => void
  onSubscriptionCreated?: () => void
  onMarkedNotSubscription?: () => void
  onBulkMarked?: () => void
}

const DETAIL_QUERY_KEY = ['uncertainEmails'] as const

export const useUncertainEmailsManagement = (
  options: UseUncertainEmailsManagementOptions = {},
) => {
  const toast = useToast()
  const queryClient = useQueryClient()

  const emailDetailMutation = useMutation({
    mutationFn: aiSandboxAPI.getEmailDetail,
    onSuccess: (data) => {
      options.onEmailDetailLoaded?.(data)
    },
    onError: () => {
      toast({
        title: 'Failed to load email details',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const createSubscriptionMutation = useMutation({
    mutationFn: aiSandboxAPI.createSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DETAIL_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      toast({
        title: 'Subscription created successfully',
        status: 'success',
        duration: 3000,
      })
      options.onSubscriptionCreated?.()
    },
    onError: (error: unknown) => {
      toast({
        title: 'Failed to create subscription',
        description: extractErrorMessage(error),
        status: 'error',
        duration: 5000,
      })
    },
  })

  const markNotSubscriptionMutation = useMutation({
    mutationFn: aiSandboxAPI.markNotSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DETAIL_QUERY_KEY })
      toast({
        title: 'Email marked as not a subscription',
        description: 'This email will be removed from uncertain emails list',
        status: 'success',
        duration: 3000,
      })
      options.onMarkedNotSubscription?.()
    },
    onError: (error: unknown) => {
      toast({
        title: 'Failed to mark email',
        description: extractErrorMessage(error),
        status: 'error',
        duration: 5000,
      })
    },
  })

  const bulkMarkNotSubscriptionMutation = useMutation({
    mutationFn: aiSandboxAPI.bulkMarkNotSubscription,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: DETAIL_QUERY_KEY })
      toast({
        title: 'Bulk operation completed',
        description: `${result.processed} emails marked as not subscriptions${
          result.failed > 0 ? `, ${result.failed} failed` : ''
        }`,
        status: result.failed > 0 ? 'warning' : 'success',
        duration: 5000,
      })
      options.onBulkMarked?.()
    },
    onError: (error: unknown) => {
      toast({
        title: 'Bulk operation failed',
        description: extractErrorMessage(error),
        status: 'error',
        duration: 5000,
      })
    },
  })

  return {
    emailDetailMutation,
    createSubscriptionMutation,
    markNotSubscriptionMutation,
    bulkMarkNotSubscriptionMutation,
  }
}

function extractErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) {
      return response.data.detail
    }
  }
  return 'Unknown error'
}
