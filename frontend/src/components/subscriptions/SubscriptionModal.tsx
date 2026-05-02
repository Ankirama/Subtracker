import { useEffect, useState } from 'react'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  VStack,
  useToast,
  Switch,
  HStack,
  NumberInput,
  NumberInputField,
} from '@chakra-ui/react'
import { subscriptionsAPI } from '../../api/subscriptions'
import { categoriesAPI } from '../../api/categories'
import { BillingCycle, Subscription, SubscriptionCreate, SubscriptionUpdate } from '../../types'

interface SubscriptionModalProps {
  isOpen: boolean
  onClose: () => void
  subscription: Subscription | null
}

export const SubscriptionModal = ({
  isOpen,
  onClose,
  subscription,
}: SubscriptionModalProps) => {
  const [formData, setFormData] = useState<{
    provider: string
    amount: string
    currency: string
    billing_cycle: BillingCycle
    category: string
    custom_label: string
    notes: string
    renewal_date: string
    is_active: boolean
  }>({
    provider: '',
    amount: '',
    currency: 'EUR',
    billing_cycle: 'monthly',
    category: 'other',
    custom_label: '',
    notes: '',
    renewal_date: '',
    is_active: true,
  })

  const queryClient = useQueryClient()
  const toast = useToast()

  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: categoriesAPI.getAll,
  })

  useEffect(() => {
    if (subscription) {
      setFormData({
        provider: subscription.provider,
        amount: subscription.amount?.toString() || '',
        currency: subscription.currency,
        billing_cycle: subscription.billing_cycle,
        category: subscription.category,
        custom_label: subscription.custom_label || '',
        notes: subscription.notes || '',
        renewal_date: subscription.renewal_date
          ? new Date(subscription.renewal_date).toISOString().split('T')[0]
          : '',
        is_active: subscription.is_active,
      })
    } else {
      // Reset form for new subscription
      setFormData({
        provider: '',
        amount: '',
        currency: 'EUR',
        billing_cycle: 'monthly',
        category: 'other',
        custom_label: '',
        notes: '',
        renewal_date: '',
        is_active: true,
      })
    }
  }, [subscription, isOpen])

  const createMutation = useMutation({
    mutationFn: subscriptionsAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      queryClient.invalidateQueries({ queryKey: ['subscriptionStats'] })
      toast({
        title: 'Subscription created',
        status: 'success',
        duration: 3000,
      })
      onClose()
    },
    onError: () => {
      toast({
        title: 'Failed to create subscription',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: SubscriptionUpdate }) =>
      subscriptionsAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      queryClient.invalidateQueries({ queryKey: ['subscriptionStats'] })
      toast({
        title: 'Subscription updated',
        status: 'success',
        duration: 3000,
      })
      onClose()
    },
    onError: () => {
      toast({
        title: 'Failed to update subscription',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const handleSubmit = () => {
    // Convert date to datetime string if provided
    let renewalDateTime = null
    if (formData.renewal_date) {
      // Convert date string (YYYY-MM-DD) to datetime string (YYYY-MM-DDTHH:MM:SS)
      renewalDateTime = `${formData.renewal_date}T00:00:00`
    }

    const data: SubscriptionCreate | SubscriptionUpdate = {
      provider: formData.provider,
      amount: formData.amount ? parseFloat(formData.amount) : null,
      currency: formData.currency,
      billing_cycle: formData.billing_cycle,
      category: formData.category,
      custom_label: formData.custom_label || null,
      notes: formData.notes || null,
      renewal_date: renewalDateTime,
    }

    if (subscription) {
      updateMutation.mutate({
        id: subscription.id,
        data: { ...data, is_active: formData.is_active },
      })
    } else {
      createMutation.mutate(data as SubscriptionCreate)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size={{ base: 'full', md: 'xl' }}
      motionPreset="slideInBottom"
    >
      <ModalOverlay />
      <ModalContent
        maxH={{ base: '100vh', md: 'auto' }}
        my={{ base: 0, md: 'auto' }}
      >
        <ModalHeader>
          {subscription ? 'Edit Subscription' : 'Add Subscription'}
        </ModalHeader>
        <ModalCloseButton />

        <ModalBody overflowY="auto" px={{ base: 4, md: 6 }} py={{ base: 4, md: 6 }}>
          <VStack spacing={4}>
            <FormControl isRequired>
              <FormLabel>Provider</FormLabel>
              <Input
                value={formData.provider}
                onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                placeholder="e.g., Netflix, Spotify"
              />
            </FormControl>

            <FormControl>
              <FormLabel>Custom Label</FormLabel>
              <Input
                value={formData.custom_label}
                onChange={(e) => setFormData({ ...formData, custom_label: e.target.value })}
                placeholder="Optional custom name"
              />
            </FormControl>

            <HStack w="full" spacing={4}>
              <FormControl>
                <FormLabel>Amount</FormLabel>
                <NumberInput
                  value={formData.amount}
                  onChange={(value) => setFormData({ ...formData, amount: value })}
                  precision={2}
                  min={0}
                >
                  <NumberInputField placeholder="0.00" />
                </NumberInput>
              </FormControl>

              <FormControl>
                <FormLabel>Currency</FormLabel>
                <Select
                  value={formData.currency}
                  onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                >
                  <option value="EUR">EUR (€)</option>
                  <option value="USD">USD ($)</option>
                  <option value="GBP">GBP (£)</option>
                </Select>
              </FormControl>
            </HStack>

            <HStack w="full" spacing={4}>
              <FormControl isRequired>
                <FormLabel>Billing Cycle</FormLabel>
                <Select
                  value={formData.billing_cycle}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      billing_cycle: e.target.value as BillingCycle,
                    })
                  }
                >
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="weekly">Weekly</option>
                  <option value="one-time">One-time</option>
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Category</FormLabel>
                <Select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                >
                  {categoriesData?.categories.map((category) => (
                    <option key={category.name} value={category.name}>
                      {category.display_name}
                    </option>
                  ))}
                </Select>
              </FormControl>
            </HStack>

            <FormControl>
              <FormLabel>Renewal Date</FormLabel>
              <Input
                type="date"
                value={formData.renewal_date}
                onChange={(e) => setFormData({ ...formData, renewal_date: e.target.value })}
              />
            </FormControl>

            <FormControl>
              <FormLabel>Notes</FormLabel>
              <Textarea
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Any additional notes..."
                rows={3}
              />
            </FormControl>

            {subscription && (
              <FormControl display="flex" alignItems="center">
                <FormLabel mb={0}>Active</FormLabel>
                <Switch
                  isChecked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
              </FormControl>
            )}
          </VStack>
        </ModalBody>

        <ModalFooter
          px={{ base: 4, md: 6 }}
          py={{ base: 4, md: 6 }}
          borderTopWidth={{ base: '1px', md: 0 }}
          position={{ base: 'sticky', md: 'relative' }}
          bottom={{ base: 0, md: 'auto' }}
          bg="white"
        >
          <Button variant="ghost" mr={3} onClick={onClose} w={{ base: 'full', md: 'auto' }}>
            Cancel
          </Button>
          <Button
            colorScheme="blue"
            onClick={handleSubmit}
            isLoading={createMutation.isPending || updateMutation.isPending}
            w={{ base: 'full', md: 'auto' }}
          >
            {subscription ? 'Save Changes' : 'Create Subscription'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}
