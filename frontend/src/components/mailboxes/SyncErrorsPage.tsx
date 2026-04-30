import { useState } from 'react'
import { useParams, Link as RouterLink } from 'react-router-dom'
import {
  Box,
  Button,
  Container,
  Flex,
  Heading,
  HStack,
  Select,
  Spinner,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tooltip,
  Tr,
  useToast,
  Tag,
  TagLabel,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'
import {
  useIgnoreSyncError,
  useRetrySyncErrors,
  useSyncErrors,
} from '../../hooks/useSyncErrors'
import {
  SyncErrorStatus,
  SyncErrorType,
} from '../../api/syncErrors'

const STATUS_FILTERS: SyncErrorStatus[] = [
  'pending',
  'retried',
  'ignored',
  'auto_recovered',
]

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

export function SyncErrorsPage() {
  const { mailboxId } = useParams<{ mailboxId: string }>()
  const { t } = useTranslation(['syncErrors', 'translation'])
  const toast = useToast()

  const [status, setStatus] = useState<SyncErrorStatus | ''>('pending')
  const [errorType, setErrorType] = useState<SyncErrorType | ''>('')

  const params = {
    ...(status && { status }),
    ...(errorType && { error_type: errorType }),
  }

  const { data, isLoading } = useSyncErrors(mailboxId ?? '', params)
  const retryMutation = useRetrySyncErrors(mailboxId ?? '')
  const ignoreMutation = useIgnoreSyncError(mailboxId ?? '')

  if (!mailboxId) return null

  const handleRetryAll = async () => {
    try {
      await retryMutation.mutateAsync()
      toast({ status: 'info', description: t('syncErrors:retry_started') })
    } catch (e) {
      toast({ status: 'error', description: String(e) })
    }
  }

  const handleIgnore = async (id: string) => {
    if (!window.confirm(t('syncErrors:actions.ignore_confirm'))) return
    try {
      await ignoreMutation.mutateAsync(id)
      toast({ status: 'success', description: t('syncErrors:ignored_toast') })
    } catch (e) {
      toast({ status: 'error', description: String(e) })
    }
  }

  return (
    <Container maxW="6xl" py={6}>
      <Flex justify="space-between" align="center" mb={4}>
        <Heading size="lg">{t('syncErrors:page_title')}</Heading>
        <Button as={RouterLink} to="/mailboxes" variant="ghost">
          {t('syncErrors:back_to_mailbox')}
        </Button>
      </Flex>

      <HStack spacing={3} mb={4}>
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value as SyncErrorStatus | '')}
          maxW="200px"
        >
          <option value="">{t('syncErrors:filters.all')}</option>
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {t(`syncErrors:status.${s}`)}
            </option>
          ))}
        </Select>
        <Select
          value={errorType}
          onChange={(e) => setErrorType(e.target.value as SyncErrorType | '')}
          maxW="240px"
        >
          <option value="">{t('syncErrors:filters.all')}</option>
          {ERROR_TYPES.map((et) => (
            <option key={et} value={et}>
              {et}
            </option>
          ))}
        </Select>
        <Button
          colorScheme="orange"
          isLoading={retryMutation.isPending}
          onClick={handleRetryAll}
        >
          {t('syncErrors:actions.retry_all')}
        </Button>
      </HStack>

      {isLoading ? (
        <Spinner />
      ) : data?.items.length === 0 ? (
        <Box>{t('syncErrors:empty')}</Box>
      ) : (
        <Table size="sm" variant="striped">
          <Thead>
            <Tr>
              <Th>{t('syncErrors:table.date')}</Th>
              <Th>{t('syncErrors:table.sender')}</Th>
              <Th>{t('syncErrors:table.subject')}</Th>
              <Th>{t('syncErrors:table.error')}</Th>
              <Th>{t('syncErrors:table.status')}</Th>
              <Th>{t('syncErrors:table.actions')}</Th>
            </Tr>
          </Thead>
          <Tbody>
            {data?.items.map((row) => (
              <Tr key={row.id}>
                <Td>{new Date(row.created_at).toLocaleString()}</Td>
                <Td>{row.sender ?? '—'}</Td>
                <Td maxW="320px" isTruncated>
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
                  {row.status === 'pending' && (
                    <Button
                      size="xs"
                      onClick={() => handleIgnore(row.id)}
                      isLoading={ignoreMutation.isPending}
                    >
                      {t('syncErrors:actions.ignore')}
                    </Button>
                  )}
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}
    </Container>
  )
}
