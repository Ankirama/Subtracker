import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Button,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  IconButton,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  useToast,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Input,
  Select,
} from '@chakra-ui/react'
import { FiPlus, FiTrash2 } from 'react-icons/fi'
import { categoriesAPI } from '../../api/categories'

// Available Chakra UI color schemes
const CHAKRA_COLORS = [
  'gray', 'red', 'orange', 'yellow', 'green', 'teal', 'blue', 'cyan',
  'purple', 'pink', 'linkedin', 'facebook', 'messenger', 'whatsapp', 'twitter', 'telegram'
]

export const CategoriesPage = () => {
  const [newCategoryName, setNewCategoryName] = useState('')
  const [newCategoryDisplayName, setNewCategoryDisplayName] = useState('')
  const [newCategoryColor, setNewCategoryColor] = useState('gray')
  const { isOpen, onOpen, onClose } = useDisclosure()

  const queryClient = useQueryClient()
  const toast = useToast()

  const { data, isLoading, error } = useQuery({
    queryKey: ['categories'],
    queryFn: categoriesAPI.getAll,
  })

  const createMutation = useMutation({
    mutationFn: categoriesAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      toast({
        title: 'Category created',
        status: 'success',
        duration: 3000,
      })
      setNewCategoryName('')
      setNewCategoryDisplayName('')
      setNewCategoryColor('gray')
      onClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to create category',
        description: error.response?.data?.detail || 'An error occurred',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: categoriesAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      toast({
        title: 'Category deleted',
        status: 'success',
        duration: 3000,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to delete category',
        description: error.response?.data?.detail || 'An error occurred',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const handleCreateCategory = () => {
    if (!newCategoryName.trim() || !newCategoryDisplayName.trim()) {
      toast({
        title: 'Please fill in all fields',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    createMutation.mutate({
      name: newCategoryName.trim(),
      display_name: newCategoryDisplayName.trim(),
      color: newCategoryColor,
    })
  }

  const handleDeleteCategory = (categoryId: string) => {
    if (window.confirm('Are you sure you want to delete this category?')) {
      deleteMutation.mutate(categoryId)
    }
  }

  if (isLoading) {
    return (
      <Center h="200px">
        <Spinner size="xl" />
      </Center>
    )
  }

  if (error) {
    return (
      <Container maxW="container.xl" py={8}>
        <Alert status="error">
          <AlertIcon />
          Failed to load categories
        </Alert>
      </Container>
    )
  }

  const categories = data?.categories || []
  const defaultCategories = categories.filter((cat) => cat.is_default)
  const customCategories = categories.filter((cat) => !cat.is_default)

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={6} align="stretch">
        <HStack justify="space-between">
          <Heading>Categories</Heading>
          <Button leftIcon={<FiPlus />} colorScheme="blue" onClick={onOpen}>
            Add Custom Category
          </Button>
        </HStack>

        <Box>
          <Heading size="md" mb={4}>
            Default Categories
          </Heading>
          <Box overflowX="auto" borderWidth={1} borderRadius="lg">
            <Table variant="simple">
              <Thead bg="gray.50">
                <Tr>
                  <Th>Name</Th>
                  <Th>Display Name</Th>
                  <Th>Color</Th>
                  <Th>Type</Th>
                </Tr>
              </Thead>
              <Tbody>
                {defaultCategories.length === 0 ? (
                  <Tr>
                    <Td colSpan={4} textAlign="center" py={4}>
                      <Text color="gray.500">No default categories</Text>
                    </Td>
                  </Tr>
                ) : (
                  defaultCategories.map((category) => (
                    <Tr key={category.name}>
                      <Td fontFamily="mono">{category.name}</Td>
                      <Td>
                        <Badge colorScheme={category.color} textTransform="capitalize">
                          {category.display_name}
                        </Badge>
                      </Td>
                      <Td>
                        <Badge colorScheme={category.color} variant="subtle">
                          {category.color}
                        </Badge>
                      </Td>
                      <Td>
                        <Badge colorScheme="blue">Default</Badge>
                      </Td>
                    </Tr>
                  ))
                )}
              </Tbody>
            </Table>
          </Box>
        </Box>

        <Box>
          <Heading size="md" mb={4}>
            Custom Categories
          </Heading>
          <Box overflowX="auto" borderWidth={1} borderRadius="lg">
            <Table variant="simple">
              <Thead bg="gray.50">
                <Tr>
                  <Th>Name</Th>
                  <Th>Display Name</Th>
                  <Th>Color</Th>
                  <Th>Type</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {customCategories.length === 0 ? (
                  <Tr>
                    <Td colSpan={5} textAlign="center" py={4}>
                      <Text color="gray.500">
                        No custom categories. Create one to get started.
                      </Text>
                    </Td>
                  </Tr>
                ) : (
                  customCategories.map((category) => (
                    <Tr key={category.id}>
                      <Td fontFamily="mono">{category.name}</Td>
                      <Td>
                        <Badge colorScheme={category.color} textTransform="capitalize">
                          {category.display_name}
                        </Badge>
                      </Td>
                      <Td>
                        <Badge colorScheme={category.color} variant="subtle">
                          {category.color}
                        </Badge>
                      </Td>
                      <Td>
                        <Badge colorScheme="purple">Custom</Badge>
                      </Td>
                      <Td>
                        <IconButton
                          aria-label="Delete category"
                          icon={<FiTrash2 />}
                          size="sm"
                          colorScheme="red"
                          variant="ghost"
                          onClick={() => handleDeleteCategory(category.id!)}
                        />
                      </Td>
                    </Tr>
                  ))
                )}
              </Tbody>
            </Table>
          </Box>
        </Box>
      </VStack>

      {/* Create Category Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create Custom Category</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Category Name</FormLabel>
                <Input
                  placeholder="e.g., gaming, health, travel"
                  value={newCategoryName}
                  onChange={(e) => setNewCategoryName(e.target.value)}
                />
                <Text fontSize="sm" color="gray.500" mt={1}>
                  Lowercase, no spaces (will be normalized)
                </Text>
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Display Name</FormLabel>
                <Input
                  placeholder="e.g., Gaming, Health & Wellness, Travel"
                  value={newCategoryDisplayName}
                  onChange={(e) => setNewCategoryDisplayName(e.target.value)}
                />
                <Text fontSize="sm" color="gray.500" mt={1}>
                  How it will appear in dropdowns
                </Text>
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Color</FormLabel>
                <HStack spacing={3}>
                  <Select
                    value={newCategoryColor}
                    onChange={(e) => setNewCategoryColor(e.target.value)}
                  >
                    {CHAKRA_COLORS.map((color) => (
                      <option key={color} value={color}>
                        {color}
                      </option>
                    ))}
                  </Select>
                  <Badge colorScheme={newCategoryColor} px={4} py={2} borderRadius="md">
                    Preview
                  </Badge>
                </HStack>
                <Text fontSize="sm" color="gray.500" mt={1}>
                  Chakra UI color scheme for the category badge
                </Text>
              </FormControl>
            </VStack>
          </ModalBody>

          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleCreateCategory}
              isLoading={createMutation.isPending}
            >
              Create
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  )
}
