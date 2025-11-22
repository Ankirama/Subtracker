import { useState } from 'react'
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
  Checkbox,
  Select,
  HStack,
  useToast,
  Text,
  Icon,
} from '@chakra-ui/react'
import { FiDownload, FiFileText, FiFile } from 'react-icons/fi'
import { exportApi, ExportFilters } from '../../api/export'

interface ExportModalProps {
  isOpen: boolean
  onClose: () => void
}

const CATEGORIES = [
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

export const ExportModal = ({ isOpen, onClose }: ExportModalProps) => {
  const toast = useToast()
  const [isExporting, setIsExporting] = useState(false)
  const [filters, setFilters] = useState<ExportFilters>({
    startDate: '',
    endDate: '',
    activeOnly: false,
    category: '',
  })

  const handleExportCSV = async () => {
    setIsExporting(true)
    try {
      const blob = await exportApi.exportCSV(filters)
      exportApi.downloadCSV(blob)
      toast({
        title: 'Export successful',
        description: 'Your subscriptions have been exported to CSV',
        status: 'success',
        duration: 3000,
      })
      onClose()
    } catch (error: any) {
      toast({
        title: 'Export failed',
        description: error.response?.data?.detail || 'Failed to export subscriptions',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsExporting(false)
    }
  }

  const handleExportPDF = async () => {
    setIsExporting(true)
    try {
      await exportApi.exportPDF(filters)
      toast({
        title: 'Opening PDF report',
        description: 'Your subscription report will open in a new tab',
        status: 'success',
        duration: 3000,
      })
      onClose()
    } catch (error: any) {
      toast({
        title: 'Export failed',
        description: error.response?.data?.detail || 'Failed to generate PDF report',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsExporting(false)
    }
  }

  const resetFilters = () => {
    setFilters({
      startDate: '',
      endDate: '',
      activeOnly: false,
      category: '',
    })
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Export Subscriptions</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4} align="stretch">
            <Text color="text.subtle" fontSize="sm">
              Export your subscription data with optional filters. Choose between CSV for data analysis or PDF for a formatted report.
            </Text>

            <FormControl>
              <FormLabel fontSize="sm">Start Date (Optional)</FormLabel>
              <Input
                type="date"
                value={filters.startDate}
                onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
                placeholder="Filter by start date"
              />
            </FormControl>

            <FormControl>
              <FormLabel fontSize="sm">End Date (Optional)</FormLabel>
              <Input
                type="date"
                value={filters.endDate}
                onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
                placeholder="Filter by end date"
              />
            </FormControl>

            <FormControl>
              <FormLabel fontSize="sm">Category (Optional)</FormLabel>
              <Select
                value={filters.category}
                onChange={(e) => setFilters({ ...filters, category: e.target.value })}
                placeholder="All categories"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </option>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <Checkbox
                isChecked={filters.activeOnly}
                onChange={(e) => setFilters({ ...filters, activeOnly: e.target.checked })}
              >
                <Text fontSize="sm">Active subscriptions only</Text>
              </Checkbox>
            </FormControl>

            {(filters.startDate || filters.endDate || filters.category || filters.activeOnly) && (
              <Button size="sm" variant="ghost" onClick={resetFilters}>
                Clear Filters
              </Button>
            )}
          </VStack>
        </ModalBody>

        <ModalFooter>
          <HStack spacing={3} width="full" justify="space-between">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <HStack spacing={3}>
              <Button
                leftIcon={<Icon as={FiFile} />}
                colorScheme="green"
                onClick={handleExportCSV}
                isLoading={isExporting}
              >
                Export CSV
              </Button>
              <Button
                leftIcon={<Icon as={FiFileText} />}
                colorScheme="blue"
                onClick={handleExportPDF}
                isLoading={isExporting}
              >
                Export PDF
              </Button>
            </HStack>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}
