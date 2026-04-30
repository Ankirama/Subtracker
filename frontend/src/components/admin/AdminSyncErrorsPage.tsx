import { useState } from 'react'
import {
  Box,
  Button,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerOverlay,
  Flex,
  Heading,
  HStack,
  Select,
  Spinner,
  Stack,
  Table,
  Tag,
  TagLabel,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
  useDisclosure,
  useToast,
  VStack,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'

import {
  useAdminSyncErrorDetail,
  useAdminSyncErrors,
  useResolveAdminSyncError,
} from '../../hooks/useAdminSyncErrors'
import {
  AdminSyncErrorListParams,
} from '../../api/adminSyncErrors'
import {
  SyncErrorSeverity,
  SyncErrorStatus,
  SyncErrorType,
} from '../../api/syncErrors'

const STATUS_FILTERS: SyncErrorStatus[] = [
  'pending',
  'retried',
  'resolved',
  'ignored',
  'auto_recovered',
]

const SEVERITY_FILTERS: SyncErrorSeverity[] = ['low', 'medium', 'high']

const ERROR_TYPES: SyncErrorType[] = [
  'schema_too_long',
  'encoding_error',
  'extraction_failed',
  'db_constraint',
  'unexpected',
]

function severityColor(s: string) {
  return s === 'high' ? 'red' : s === 'medium' ? 'orange' : 'gray'
}

function truncate(value: string, max = 12): string {
  if (value.length <= max) return value
  return `${value.slice(0, max)}…`
}

export const AdminSyncErrorsPage = () => {
  const { t } = useTranslation(['adminSyncErrors', 'syncErrors', 'translation'])
  const toast = useToast()
  const drawer = useDisclosure()

  const [status, setStatus] = useState<SyncErrorStatus | ''>('pending')
  const [severity, setSeverity] = useState<SyncErrorSeverity | ''>('')
  const [errorType, setErrorType] = useState<SyncErrorType | ''>('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const params: AdminSyncErrorListParams = {
    ...(status && { status }),
    ...(severity && { severity }),
    ...(errorType && { error_type: errorType }),
  }

  const { data, isLoading } = useAdminSyncErrors(params)
  const detailQuery = useAdminSyncErrorDetail(selectedId)
  const resolveMutation = useResolveAdminSyncError()

  const openDrawer = (id: string) => {
    setSelectedId(id)
    drawer.onOpen()
  }

  const closeDrawer = () => {
    drawer.onClose()
    setSelectedId(null)
  }

  const handleResolve = async () => {
    if (!selectedId) return
    try {
      await resolveMutation.mutateAsync(selectedId)
      toast({
        status: 'success',
        description: t('adminSyncErrors:drawer.resolved_toast'),
      })
      closeDrawer()
    } catch (e) {
      toast({ status: 'error', description: String(e) })
    }
  }

  const detail = detailQuery.data

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={4}>
        <Heading size="lg">{t('adminSyncErrors:page_title')}</Heading>
        {data && (
          <Text fontSize="sm" color="gray.500">
            {t('adminSyncErrors:total', { count: data.total })}
          </Text>
        )}
      </Flex>

      <HStack spacing={3} mb={4}>
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value as SyncErrorStatus | '')}
          maxW="200px"
          aria-label={t('adminSyncErrors:filters.status')}
        >
          <option value="">{t('adminSyncErrors:filters.all')}</option>
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {t(`syncErrors:status.${s}`)}
            </option>
          ))}
        </Select>
        <Select
          value={severity}
          onChange={(e) =>
            setSeverity(e.target.value as SyncErrorSeverity | '')
          }
          maxW="180px"
          aria-label={t('adminSyncErrors:filters.severity')}
        >
          <option value="">{t('adminSyncErrors:filters.all')}</option>
          {SEVERITY_FILTERS.map((sev) => (
            <option key={sev} value={sev}>
              {t(`adminSyncErrors:severity.${sev}`)}
            </option>
          ))}
        </Select>
        <Select
          value={errorType}
          onChange={(e) => setErrorType(e.target.value as SyncErrorType | '')}
          maxW="240px"
          aria-label={t('adminSyncErrors:filters.error_type')}
        >
          <option value="">{t('adminSyncErrors:filters.all')}</option>
          {ERROR_TYPES.map((et) => (
            <option key={et} value={et}>
              {et}
            </option>
          ))}
        </Select>
      </HStack>

      {isLoading ? (
        <Spinner />
      ) : !data || data.items.length === 0 ? (
        <Box color="gray.500">{t('adminSyncErrors:empty')}</Box>
      ) : (
        <Box overflowX="auto">
          <Table size="sm" variant="striped">
            <Thead>
              <Tr>
                <Th>{t('adminSyncErrors:table.date')}</Th>
                <Th>{t('adminSyncErrors:table.mailbox')}</Th>
                <Th>{t('adminSyncErrors:table.sender')}</Th>
                <Th>{t('adminSyncErrors:table.subject')}</Th>
                <Th>{t('adminSyncErrors:table.error')}</Th>
                <Th>{t('adminSyncErrors:table.status')}</Th>
                <Th>{t('adminSyncErrors:table.severity')}</Th>
              </Tr>
            </Thead>
            <Tbody>
              {data.items.map((row) => (
                <Tr
                  key={row.id}
                  cursor="pointer"
                  _hover={{ bg: 'blackAlpha.50' }}
                  onClick={() => openDrawer(row.id)}
                >
                  <Td>{new Date(row.created_at).toLocaleString()}</Td>
                  <Td>
                    <Tooltip label={row.mailbox_id}>
                      <Text fontFamily="mono" fontSize="xs">
                        {truncate(row.mailbox_id, 8)}
                      </Text>
                    </Tooltip>
                  </Td>
                  <Td>{row.sender ?? '—'}</Td>
                  <Td maxW="280px" isTruncated>
                    {row.subject ?? '—'}
                  </Td>
                  <Td>
                    <Tooltip
                      label={t(`syncErrors:error_types.${row.error_type}`)}
                    >
                      <Tag colorScheme={severityColor(row.severity)}>
                        <TagLabel>{row.error_type}</TagLabel>
                      </Tag>
                    </Tooltip>
                  </Td>
                  <Td>{t(`syncErrors:status.${row.status}`)}</Td>
                  <Td>
                    <Tag colorScheme={severityColor(row.severity)} size="sm">
                      <TagLabel>
                        {t(`adminSyncErrors:severity.${row.severity}`)}
                      </TagLabel>
                    </Tag>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}

      <Drawer
        isOpen={drawer.isOpen}
        placement="right"
        onClose={closeDrawer}
        size="md"
      >
        <DrawerOverlay />
        <DrawerContent>
          <DrawerCloseButton />
          <DrawerHeader>{t('adminSyncErrors:drawer.title')}</DrawerHeader>
          <DrawerBody>
            {detailQuery.isLoading || !detail ? (
              <Spinner />
            ) : (
              <VStack align="stretch" spacing={5}>
                <Box>
                  <Heading size="sm" mb={2}>
                    {t('adminSyncErrors:drawer.summary')}
                  </Heading>
                  <Stack spacing={1} fontSize="sm">
                    <Text>
                      <strong>{t('adminSyncErrors:table.date')}:</strong>{' '}
                      {new Date(detail.created_at).toLocaleString()}
                    </Text>
                    <Text>
                      <strong>{t('adminSyncErrors:table.mailbox')}:</strong>{' '}
                      <Text as="span" fontFamily="mono" fontSize="xs">
                        {detail.mailbox_id}
                      </Text>
                    </Text>
                    <Text>
                      <strong>{t('adminSyncErrors:table.sender')}:</strong>{' '}
                      {detail.sender ?? '—'}
                    </Text>
                    <Text>
                      <strong>{t('adminSyncErrors:table.subject')}:</strong>{' '}
                      {detail.subject ?? '—'}
                    </Text>
                    <Text>
                      <strong>{t('adminSyncErrors:table.error')}:</strong>{' '}
                      <Tag
                        colorScheme={severityColor(detail.severity)}
                        size="sm"
                      >
                        <TagLabel>{detail.error_type}</TagLabel>
                      </Tag>
                    </Text>
                    <Text>
                      <strong>{t('adminSyncErrors:table.status')}:</strong>{' '}
                      {t(`syncErrors:status.${detail.status}`)}
                    </Text>
                    <Text>
                      <strong>{t('adminSyncErrors:table.severity')}:</strong>{' '}
                      {t(`adminSyncErrors:severity.${detail.severity}`)}
                    </Text>
                    <Text>
                      <strong>{t('syncErrors:table.error')}:</strong>{' '}
                      {detail.error_message}
                    </Text>
                    {detail.resolved_at && (
                      <Text>
                        <strong>
                          {t('adminSyncErrors:drawer.resolved_at')}:
                        </strong>{' '}
                        {new Date(detail.resolved_at).toLocaleString()}
                      </Text>
                    )}
                    {detail.resolved_by_id && (
                      <Text>
                        <strong>
                          {t('adminSyncErrors:drawer.resolved_by')}:
                        </strong>{' '}
                        <Text as="span" fontFamily="mono" fontSize="xs">
                          {detail.resolved_by_id}
                        </Text>
                      </Text>
                    )}
                  </Stack>
                </Box>

                <Box>
                  <Heading size="sm" mb={2}>
                    {t('adminSyncErrors:drawer.stack_trace')}
                  </Heading>
                  {detail.stack_trace ? (
                    <Box
                      as="pre"
                      whiteSpace="pre-wrap"
                      fontSize="xs"
                      fontFamily="mono"
                      bg="blackAlpha.50"
                      p={3}
                      borderRadius="md"
                      overflowX="auto"
                    >
                      {detail.stack_trace}
                    </Box>
                  ) : (
                    <Text color="gray.500">—</Text>
                  )}
                </Box>

                <Box>
                  <Heading size="sm" mb={2}>
                    {t('adminSyncErrors:drawer.raw_payload')}
                  </Heading>
                  {detail.raw_payload ? (
                    <Box
                      as="pre"
                      whiteSpace="pre-wrap"
                      fontSize="xs"
                      fontFamily="mono"
                      bg="blackAlpha.50"
                      p={3}
                      borderRadius="md"
                      overflowX="auto"
                    >
                      {JSON.stringify(detail.raw_payload, null, 2)}
                    </Box>
                  ) : (
                    <Text color="gray.500">—</Text>
                  )}
                </Box>
              </VStack>
            )}
          </DrawerBody>
          <DrawerFooter>
            {detail && detail.status !== 'resolved' && (
              <Button
                colorScheme="green"
                isLoading={resolveMutation.isPending}
                onClick={handleResolve}
              >
                {t('adminSyncErrors:drawer.mark_resolved')}
              </Button>
            )}
          </DrawerFooter>
        </DrawerContent>
      </Drawer>
    </Box>
  )
}
