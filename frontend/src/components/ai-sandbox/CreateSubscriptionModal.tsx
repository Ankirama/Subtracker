import { useEffect, useState } from 'react'
import {
  Button,
  FormControl,
  FormLabel,
  HStack,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Select,
  Textarea,
  VStack,
  useToast,
} from '@chakra-ui/react'

import type { BillingCycle, EmailDetailResponse, ManualSubscriptionCreate } from '../../types'

interface CreateSubscriptionModalProps {
  email: EmailDetailResponse | null
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: ManualSubscriptionCreate) => void
  isSubmitting: boolean
}

interface FormState {
  provider: string
  amount: string
  currency: string
  billing_cycle: BillingCycle
  renewal_date: string
  custom_label: string
  category: string
  notes: string
}

const INITIAL_FORM: FormState = {
  provider: '',
  amount: '',
  currency: 'EUR',
  billing_cycle: 'monthly',
  renewal_date: '',
  custom_label: '',
  category: 'other',
  notes: '',
}

export const CreateSubscriptionModal = ({
  email,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
}: CreateSubscriptionModalProps) => {
  const toast = useToast()
  const [formData, setFormData] = useState<FormState>(INITIAL_FORM)

  useEffect(() => {
    if (isOpen) {
      setFormData(INITIAL_FORM)
    }
  }, [isOpen])

  const handleSubmit = () => {
    if (!email) return
    if (!formData.provider) {
      toast({ title: 'Provider is required', status: 'warning', duration: 3000 })
      return
    }

    const renewalDateTime = formData.renewal_date
      ? new Date(`${formData.renewal_date}T00:00:00`).toISOString()
      : null

    onSubmit({
      email_id: email.id,
      provider: formData.provider,
      amount: formData.amount ? parseFloat(formData.amount) : null,
      currency: formData.currency || null,
      billing_cycle: formData.billing_cycle || null,
      renewal_date: renewalDateTime,
      custom_label: formData.custom_label || null,
      category: formData.category || 'other',
      notes: formData.notes || null,
    })
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Create Subscription Manually</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4}>
            <FormControl isRequired>
              <FormLabel>Provider</FormLabel>
              <Input
                placeholder="Service name (e.g., Netflix, Spotify)"
                value={formData.provider}
                onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
              />
            </FormControl>

            <HStack w="full" spacing={4}>
              <FormControl flex={2}>
                <FormLabel>Amount</FormLabel>
                <Input
                  type="number"
                  step="0.01"
                  placeholder="9.99"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                />
              </FormControl>

              <FormControl flex={1}>
                <FormLabel>Currency</FormLabel>
                <Select
                  value={formData.currency}
                  onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                >
                  <option value="EUR">EUR</option>
                  <option value="USD">USD</option>
                  <option value="GBP">GBP</option>
                </Select>
              </FormControl>
            </HStack>

            <FormControl>
              <FormLabel>Billing Cycle</FormLabel>
              <Select
                value={formData.billing_cycle}
                onChange={(e) =>
                  setFormData({ ...formData, billing_cycle: e.target.value as BillingCycle })
                }
              >
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
                <option value="weekly">Weekly</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Renewal Date</FormLabel>
              <Input
                type="date"
                value={formData.renewal_date}
                onChange={(e) => setFormData({ ...formData, renewal_date: e.target.value })}
              />
            </FormControl>

            <FormControl>
              <FormLabel>Custom Label</FormLabel>
              <Input
                placeholder="e.g., Family Plan, Premium Tier"
                value={formData.custom_label}
                onChange={(e) => setFormData({ ...formData, custom_label: e.target.value })}
              />
            </FormControl>

            <FormControl>
              <FormLabel>Category</FormLabel>
              <Select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              >
                <option value="streaming">Streaming</option>
                <option value="software">Software</option>
                <option value="storage">Storage</option>
                <option value="productivity">Productivity</option>
                <option value="entertainment">Entertainment</option>
                <option value="fitness">Fitness</option>
                <option value="gaming">Gaming</option>
                <option value="news">News</option>
                <option value="education">Education</option>
                <option value="music">Music</option>
                <option value="other">Other</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Notes</FormLabel>
              <Textarea
                placeholder="Additional notes..."
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows={3}
              />
            </FormControl>
          </VStack>
        </ModalBody>
        <ModalFooter>
          <Button colorScheme="blue" onClick={handleSubmit} isLoading={isSubmitting} mr={3}>
            Create Subscription
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}
