import { useState, useEffect } from 'react'
import {
  Box,
  Heading,
  VStack,
  HStack,
  FormControl,
  FormLabel,
  Input,
  Select,
  useToast,
  Card,
  CardBody,
  Text,
  Badge,
  useColorModeValue,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Center,
  Flex,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  IconButton,
  Tooltip,
} from '@chakra-ui/react'
import {
  FiFileText,
  FiAlertCircle,
  FiAlertTriangle,
  FiInfo,
  FiChevronsLeft,
  FiChevronLeft,
  FiChevronRight,
  FiChevronsRight,
  FiRefreshCw,
} from 'react-icons/fi'
import { adminApi, type LogEntry } from '../../api/admin'

const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

const LOG_LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'gray',
  INFO: 'blue',
  WARNING: 'orange',
  ERROR: 'red',
  CRITICAL: 'purple',
}

export const AdminLogsPage = () => {
  // State
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [stats, setStats] = useState<{
    errors_24h: number
    warnings_24h: number
    total_logs: number
  } | null>(null)
  const [sources, setSources] = useState<
    Array<{ name: string; label: string; available: boolean }>
  >([])
  const [isLoading, setIsLoading] = useState(true)

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(50)
  const [totalPages, setTotalPages] = useState(1)
  const [totalLogs, setTotalLogs] = useState(0)

  // Filters
  const [selectedSource, setSelectedSource] = useState('app')
  const [selectedLevel, setSelectedLevel] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')

  const toast = useToast()
  const bgColor = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  // Load logs
  const loadLogs = async () => {
    try {
      setIsLoading(true)
      const response = await adminApi.getLogs({
        page: currentPage,
        page_size: pageSize,
        level: selectedLevel || undefined,
        search: searchQuery || undefined,
        source: selectedSource,
      })
      setLogs(response.logs)
      setTotalPages(response.total_pages)
      setTotalLogs(response.total)
    } catch (error) {
      toast({
        title: 'Error Loading Logs',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Load stats
  const loadStats = async () => {
    try {
      const statsData = await adminApi.getLogStats()
      setStats(statsData)
    } catch (error) {
      console.error('Error loading stats:', error)
    }
  }

  // Load sources
  const loadSources = async () => {
    try {
      const sourcesData = await adminApi.getLogSources()
      setSources(sourcesData.sources)
    } catch (error) {
      console.error('Error loading sources:', error)
    }
  }

  // Initial load
  useEffect(() => {
    loadLogs()
    loadStats()
    loadSources()
  }, [currentPage, selectedSource, selectedLevel, searchQuery])

  // Format timestamp
  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  // Refresh logs
  const handleRefresh = () => {
    setCurrentPage(1)
    loadLogs()
    loadStats()
  }

  return (
    <Box>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between">
          <Heading size="lg">
            <HStack>
              <FiFileText />
              <Text>System Logs</Text>
            </HStack>
          </Heading>
          <Tooltip label="Refresh Logs">
            <IconButton
              aria-label="Refresh logs"
              icon={<FiRefreshCw />}
              onClick={handleRefresh}
              colorScheme="blue"
              variant="outline"
            />
          </Tooltip>
        </HStack>

        {/* Statistics Cards */}
        {stats && (
          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiAlertCircle />
                      <Text>Errors (24h)</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber color="red.500">{stats.errors_24h}</StatNumber>
                  <StatHelpText>Last 24 hours</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiAlertTriangle />
                      <Text>Warnings (24h)</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber color="orange.500">{stats.warnings_24h}</StatNumber>
                  <StatHelpText>Last 24 hours</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiInfo />
                      <Text>Total Logs</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber color="blue.500">{stats.total_logs}</StatNumber>
                  <StatHelpText>In current source</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Filters */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
          <CardBody>
            <VStack spacing={4} align="stretch">
              <Heading size="sm">Filters</Heading>
              <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                <FormControl>
                  <FormLabel>Log Source</FormLabel>
                  <Select
                    value={selectedSource}
                    onChange={(e) => {
                      setSelectedSource(e.target.value)
                      setCurrentPage(1)
                    }}
                  >
                    {sources.map((source) => (
                      <option
                        key={source.name}
                        value={source.name}
                        disabled={!source.available}
                      >
                        {source.label}
                        {!source.available && ' (unavailable)'}
                      </option>
                    ))}
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>Log Level</FormLabel>
                  <Select
                    value={selectedLevel}
                    onChange={(e) => {
                      setSelectedLevel(e.target.value)
                      setCurrentPage(1)
                    }}
                  >
                    <option value="">All Levels</option>
                    {LOG_LEVELS.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>Search Messages</FormLabel>
                  <Input
                    placeholder="Search log messages..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value)
                      setCurrentPage(1)
                    }}
                  />
                </FormControl>
              </SimpleGrid>
            </VStack>
          </CardBody>
        </Card>

        {/* Logs Table */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
          <CardBody>
            {isLoading ? (
              <Center py={10}>
                <Spinner size="xl" />
              </Center>
            ) : logs.length === 0 ? (
              <Center py={10}>
                <Text color="gray.500">No logs found</Text>
              </Center>
            ) : (
              <Box overflowX="auto">
                <Table variant="simple" size="sm">
                  <Thead>
                    <Tr>
                      <Th width="180px">Timestamp</Th>
                      <Th width="100px">Level</Th>
                      <Th width="200px">Module</Th>
                      <Th>Message</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {logs.map((log) => (
                      <Tr key={log.id}>
                        <Td>
                          <Text fontSize="xs" fontFamily="mono" color="text.subtle">
                            {formatTimestamp(log.timestamp)}
                          </Text>
                        </Td>
                        <Td>
                          <Badge colorScheme={LOG_LEVEL_COLORS[log.level] || 'gray'}>
                            {log.level}
                          </Badge>
                        </Td>
                        <Td>
                          <Text fontSize="xs" fontFamily="mono">
                            {log.module}
                          </Text>
                        </Td>
                        <Td>
                          <Text
                            fontSize="sm"
                            fontFamily="mono"
                            whiteSpace="pre-wrap"
                            wordBreak="break-word"
                          >
                            {log.message}
                          </Text>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <Flex justify="space-between" align="center" mt={4}>
                <Text fontSize="sm" color="text.subtle">
                  Showing page {currentPage} of {totalPages} ({totalLogs} total logs)
                </Text>
                <HStack spacing={2}>
                  <IconButton
                    aria-label="First page"
                    icon={<FiChevronsLeft />}
                    size="sm"
                    onClick={() => setCurrentPage(1)}
                    isDisabled={currentPage === 1}
                  />
                  <IconButton
                    aria-label="Previous page"
                    icon={<FiChevronLeft />}
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    isDisabled={currentPage === 1}
                  />
                  <Text fontSize="sm" fontWeight="medium">
                    {currentPage}
                  </Text>
                  <IconButton
                    aria-label="Next page"
                    icon={<FiChevronRight />}
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    isDisabled={currentPage === totalPages}
                  />
                  <IconButton
                    aria-label="Last page"
                    icon={<FiChevronsRight />}
                    size="sm"
                    onClick={() => setCurrentPage(totalPages)}
                    isDisabled={currentPage === totalPages}
                  />
                </HStack>
              </Flex>
            )}
          </CardBody>
        </Card>

        {/* Info Box */}
        <Card bg="bg.accent.blue" borderColor="blue.200" borderWidth="1px">
          <CardBody>
            <VStack align="start" spacing={2}>
              <Text fontWeight="bold" color="blue.800">
                Log Viewing Tips
              </Text>
              <Text fontSize="sm" color="blue.700">
                • Logs are displayed in reverse chronological order (newest first)
              </Text>
              <Text fontSize="sm" color="blue.700">
                • Use filters to narrow down specific issues or time periods
              </Text>
              <Text fontSize="sm" color="blue.700">
                • ERROR and CRITICAL levels indicate issues requiring attention
              </Text>
              <Text fontSize="sm" color="blue.700">
                • Search is case-insensitive and searches within log messages
              </Text>
            </VStack>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  )
}
