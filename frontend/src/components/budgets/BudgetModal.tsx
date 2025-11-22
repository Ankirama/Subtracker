import { useState, useEffect } from 'react'
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  VStack,
  FormControl,
  FormLabel,
  Input,
  Select,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Switch,
  HStack,
  Text,
  useToast,
} from '@chakra-ui/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { budgetsAPI, Budget, BudgetCreate, BudgetUpdate } from '../../api/budgets'

interface BudgetModalProps {
  isOpen: boolean
  onClose: () => void
  budget?: Budget | null
}

const CATEGORIES = [
  '',
  'streaming',
  'software',
  'storage',
  'productivity',
  'entertainment',
  'fitness',
  'gaming',
  'news',
  'education',
  'communication',
  'finance',
  'shopping',
  'music',
  'other',
]

export const BudgetModal = ({ isOpen, onClose, budget }: BudgetModalProps) => {
  const toast = useToast()
  const queryClient = useQueryClient()

  const [formData, setFormData] = useState<BudgetCreate>({
    name: '',
    category: null,
    period: 'monthly',
    limit_amount: 50,
    currency: 'EUR',
    alert_threshold: 80,
    alert_enabled: true,
  })

  // Reset form when budget changes or modal opens
  useEffect(() => {
    if (budget) {
      setFormData({
        name: budget.name,
        category: budget.category,
        period: budget.period,
        limit_amount: budget.limit_amount,
        currency: budget.currency,
        alert_threshold: budget.alert_threshold,
        alert_enabled: budget.alert_enabled,
      })
    } else {
      setFormData({
        name: '',
        category: null,
        period: 'monthly',
        limit_amount: 50,
        currency: 'EUR',
        alert_threshold: 80,
        alert_enabled: true,
      })
    }
  }, [budget, isOpen])

  const createMutation = useMutation({
    mutationFn: budgetsAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
      queryClient.invalidateQueries({ queryKey: ['budgetStatuses'] })
      toast({
        title: 'Budget created',
        status: 'success',
        duration: 3000,
      })
      onClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to create budget',
        description: error.response?.data?.detail || 'Please try again',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: BudgetUpdate }) =>
      budgetsAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
      queryClient.invalidateQueries({ queryKey: ['budgetStatuses'] })
      toast({
        title: 'Budget updated',
        status: 'success',
        duration: 3000,
      })
      onClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to update budget',
        description: error.response?.data?.detail || 'Please try again',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const handleSubmit = () => {
    if (!formData.name || !formData.limit_amount) {
      toast({
        title: 'Validation error',
        description: 'Name and limit amount are required',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    if (budget) {
      updateMutation.mutate({ id: budget.id, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size={{ base: 'full', md: 'lg' }}
      motionPreset="slideInBottom"
    >
      <ModalOverlay />
      <ModalContent
        maxH={{ base: '100vh', md: 'auto' }}
        my={{ base: 0, md: 'auto' }}
      >
        <ModalHeader>{budget ? 'Edit Budget' : 'Create Budget'}</ModalHeader>
        <ModalCloseButton />
        <ModalBody overflowY="auto" px={{ base: 4, md: 6 }} py={{ base: 4, md: 6 }}>
          <VStack spacing={4} align="stretch">
            <FormControl isRequired>
              <FormLabel>Budget Name</FormLabel>
              <Input
                placeholder="e.g., Entertainment Budget"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </FormControl>

            <FormControl>
              <FormLabel>Category (Optional)</FormLabel>
              <Select
                placeholder="All categories (overall budget)"
                value={formData.category || ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    category: e.target.value || null,
                  })
                }
              >
                {CATEGORIES.filter((c) => c !== '').map((cat) => (
                  <option key={cat} value={cat}>
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </option>
                ))}
              </Select>
              <Text fontSize="sm" color="text.subtle" mt={1}>
                Leave empty for an overall budget across all categories
              </Text>
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Budget Period</FormLabel>
              <Select
                value={formData.period}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    period: e.target.value as 'monthly' | 'quarterly' | 'yearly',
                  })
                }
              >
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="yearly">Yearly</option>
              </Select>
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Budget Limit ({formData.currency})</FormLabel>
              <NumberInput
                value={formData.limit_amount}
                min={0}
                precision={2}
                onChange={(_, valueAsNumber) =>
                  setFormData({ ...formData, limit_amount: valueAsNumber || 0 })
                }
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
            </FormControl>

            <FormControl>
              <FormLabel>Alert Threshold (%)</FormLabel>
              <NumberInput
                value={formData.alert_threshold}
                min={0}
                max={100}
                onChange={(_, valueAsNumber) =>
                  setFormData({ ...formData, alert_threshold: valueAsNumber || 80 })
                }
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <Text fontSize="sm" color="text.subtle" mt={1}>
                Get alerted when spending reaches this percentage
              </Text>
            </FormControl>

            <FormControl>
              <HStack justify="space-between">
                <FormLabel mb={0}>Enable Alerts</FormLabel>
                <Switch
                  isChecked={formData.alert_enabled}
                  onChange={(e) =>
                    setFormData({ ...formData, alert_enabled: e.target.checked })
                  }
                />
              </HStack>
            </FormControl>
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
            isLoading={isLoading}
            loadingText={budget ? 'Updating...' : 'Creating...'}
            w={{ base: 'full', md: 'auto' }}
          >
            {budget ? 'Update' : 'Create'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}
