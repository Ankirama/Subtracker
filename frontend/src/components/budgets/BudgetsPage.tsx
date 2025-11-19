import { useState } from 'react'
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Button,
  Icon,
  Text,
  SimpleGrid,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Spinner,
  Center,
  useDisclosure,
  useToast,
  Divider,
} from '@chakra-ui/react'
import { FiPlus, FiAlertTriangle } from 'react-icons/fi'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { budgetsAPI, Budget, BudgetStatus } from '../../api/budgets'
import { BudgetCard } from './BudgetCard'
import { BudgetModal } from './BudgetModal'
import { BudgetSummary } from './BudgetSummary'
import { BudgetCharts } from './BudgetCharts'

export const BudgetsPage = () => {
  const toast = useToast()
  const queryClient = useQueryClient()
  const { isOpen, onOpen, onClose } = useDisclosure()
  const [selectedBudget, setSelectedBudget] = useState<Budget | null>(null)

  // Fetch budget statuses
  const { data: budgetStatuses, isLoading, error } = useQuery({
    queryKey: ['budgetStatuses'],
    queryFn: budgetsAPI.getAllStatus,
  })

  // Fetch alerts
  const { data: alerts } = useQuery({
    queryKey: ['budgetAlerts'],
    queryFn: budgetsAPI.getAlerts,
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: budgetsAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
      queryClient.invalidateQueries({ queryKey: ['budgetStatuses'] })
      queryClient.invalidateQueries({ queryKey: ['budgetAlerts'] })
      toast({
        title: 'Budget deleted',
        status: 'success',
        duration: 3000,
      })
    },
    onError: () => {
      toast({
        title: 'Failed to delete budget',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const handleNewBudget = () => {
    setSelectedBudget(null)
    onOpen()
  }

  const handleEditBudget = (budgetStatus: BudgetStatus) => {
    // Fetch the full budget object for editing
    budgetsAPI.getById(budgetStatus.budget_id).then((budget) => {
      setSelectedBudget(budget)
      onOpen()
    })
  }

  const handleDeleteBudget = (budgetId: string) => {
    if (window.confirm('Are you sure you want to delete this budget?')) {
      deleteMutation.mutate(budgetId)
    }
  }

  if (isLoading) {
    return (
      <Center h="100vh">
        <Spinner size="xl" color="blue.500" />
      </Center>
    )
  }

  if (error) {
    return (
      <Container maxW="container.xl" py={8}>
        <Alert status="error">
          <AlertIcon />
          Failed to load budgets. Please try again.
        </Alert>
      </Container>
    )
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <HStack justify="space-between">
          <Box>
            <Heading size="lg">Budget Management</Heading>
            <Text color="gray.600">
              Track your subscription spending and set limits
            </Text>
          </Box>
          <Button
            leftIcon={<Icon as={FiPlus} />}
            colorScheme="blue"
            onClick={handleNewBudget}
          >
            Create Budget
          </Button>
        </HStack>

        {/* Alerts Section */}
        {alerts && alerts.length > 0 && (
          <VStack align="stretch" spacing={3}>
            {alerts.map((alert) => (
              <Alert
                key={alert.budget.budget_id}
                status={alert.alert_type === 'exceeded' ? 'error' : 'warning'}
                borderRadius="md"
              >
                <AlertIcon as={FiAlertTriangle} />
                <Box flex="1">
                  <AlertTitle>{alert.budget.name}</AlertTitle>
                  <AlertDescription>{alert.message}</AlertDescription>
                </Box>
              </Alert>
            ))}
          </VStack>
        )}

        {/* Budget Summary Dashboard */}
        {budgetStatuses && budgetStatuses.length > 0 && (
          <>
            <BudgetSummary budgetStatuses={budgetStatuses} />
            <Divider />
            <BudgetCharts budgetStatuses={budgetStatuses} />
            <Divider />
          </>
        )}

        {/* Budgets Grid */}
        {budgetStatuses && budgetStatuses.length > 0 ? (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
            {budgetStatuses.map((budgetStatus) => (
              <BudgetCard
                key={budgetStatus.budget_id}
                budgetStatus={budgetStatus}
                onEdit={() => handleEditBudget(budgetStatus)}
                onDelete={() => handleDeleteBudget(budgetStatus.budget_id)}
              />
            ))}
          </SimpleGrid>
        ) : (
          <Box textAlign="center" py={12}>
            <Icon as={FiAlertTriangle} boxSize={12} color="gray.400" mb={4} />
            <Heading size="md" mb={2} color="gray.600">
              No budgets yet
            </Heading>
            <Text color="gray.500" mb={4}>
              Create your first budget to start tracking spending
            </Text>
            <Button
              leftIcon={<Icon as={FiPlus} />}
              colorScheme="blue"
              onClick={handleNewBudget}
            >
              Create Budget
            </Button>
          </Box>
        )}
      </VStack>

      {/* Budget Modal */}
      <BudgetModal
        isOpen={isOpen}
        onClose={onClose}
        budget={selectedBudget}
      />
    </Container>
  )
}
