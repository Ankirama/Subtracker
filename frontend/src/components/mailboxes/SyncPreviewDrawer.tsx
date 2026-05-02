import {
  Badge,
  Box,
  Card,
  CardBody,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
  DrawerOverlay,
  Flex,
  Heading,
  HStack,
  Spinner,
  Stack,
  Tag,
  Text,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useSyncPreview } from '../../hooks/useSyncPreview'
import {
  ConfidenceBucket,
  NewSubscriptionPreview,
  UpdatedSubscriptionPreview,
} from '../../api/syncPreview'

interface Props {
  syncHistoryId: string | null
  isOpen: boolean
  onClose: () => void
}

const bucketColor = (bucket: ConfidenceBucket): string =>
  bucket === 'auto_saved' ? 'green' : 'orange'

const formatAmount = (value: unknown, currency: string): string => {
  if (typeof value !== 'number') return '—'
  return `${value.toFixed(2)} ${currency}`
}

export const SyncPreviewDrawer = ({ syncHistoryId, isOpen, onClose }: Props) => {
  const { t } = useTranslation(['syncPreview'])
  const navigate = useNavigate()
  const { data, isLoading } = useSyncPreview(syncHistoryId)

  const goToSubscription = (id: string) => {
    onClose()
    navigate(`/subscriptions/${id}`)
  }

  const renderNewCard = (row: NewSubscriptionPreview) => (
    <Card
      key={row.id}
      cursor="pointer"
      _hover={{ bg: 'blackAlpha.50' }}
      onClick={() => goToSubscription(row.id)}
      size="sm"
    >
      <CardBody>
        <Flex justify="space-between" align="start">
          <Box>
            <Text fontWeight="semibold">
              {row.provider}
              {row.custom_label ? ` — ${row.custom_label}` : ''}
            </Text>
            <Text fontSize="sm" color="gray.600">
              {formatAmount(row.amount, row.currency)} · {row.billing_cycle}
              {row.category ? ` · ${row.category}` : ''}
            </Text>
            {row.source_email_subject && (
              <Text fontSize="xs" color="gray.500" mt={1} noOfLines={1}>
                {row.source_email_subject}
              </Text>
            )}
          </Box>
          <Badge colorScheme={bucketColor(row.confidence_bucket)}>
            {t(`syncPreview:badge_${row.confidence_bucket}`)}
          </Badge>
        </Flex>
      </CardBody>
    </Card>
  )

  const renderUpdatedCard = (row: UpdatedSubscriptionPreview) => {
    const changeText =
      row.update_type === 'price_change'
        ? t('syncPreview:update_price_change', {
            before: row.before.amount ?? '—',
            after: row.after.amount ?? '—',
          })
        : t('syncPreview:update_cancellation')
    return (
      <Card
        key={row.id}
        cursor="pointer"
        _hover={{ bg: 'blackAlpha.50' }}
        onClick={() => goToSubscription(row.id)}
        size="sm"
      >
        <CardBody>
          <Text fontWeight="semibold">{row.provider}</Text>
          <Text fontSize="sm" color="orange.700">
            {changeText}
          </Text>
          {row.source_email_subject && (
            <Text fontSize="xs" color="gray.500" mt={1} noOfLines={1}>
              {row.source_email_subject}
            </Text>
          )}
        </CardBody>
      </Card>
    )
  }

  const subtitle = data
    ? t('syncPreview:subtitle', {
        mailboxEmail: data.sync_history.mailbox_email,
        when: data.sync_history.completed_at
          ? new Date(data.sync_history.completed_at).toLocaleString()
          : '—',
      })
    : ''

  const isEmpty =
    !!data &&
    data.new_subscriptions.length === 0 &&
    data.updated_subscriptions.length === 0

  return (
    <Drawer isOpen={isOpen} placement="right" size="lg" onClose={onClose}>
      <DrawerOverlay />
      <DrawerContent>
        <DrawerCloseButton />
        <DrawerHeader>
          <Heading size="md">{t('syncPreview:drawer_title')}</Heading>
          <Text fontSize="sm" color="gray.600" fontWeight="normal">
            {subtitle}
          </Text>
        </DrawerHeader>
        <DrawerBody>
          {isLoading || !data ? (
            <Flex justify="center" py={8}>
              <Spinner />
            </Flex>
          ) : isEmpty ? (
            <Text color="gray.500">{t('syncPreview:empty')}</Text>
          ) : (
            <Stack spacing={6}>
              {data.new_subscriptions.length > 0 && (
                <Box>
                  <HStack mb={3}>
                    <Heading size="sm">{t('syncPreview:section_new')}</Heading>
                    <Tag colorScheme="green">+{data.new_subscriptions.length}</Tag>
                  </HStack>
                  <Stack spacing={2}>
                    {data.new_subscriptions.map(renderNewCard)}
                  </Stack>
                </Box>
              )}
              {data.updated_subscriptions.length > 0 && (
                <Box>
                  <HStack mb={3}>
                    <Heading size="sm">{t('syncPreview:section_updated')}</Heading>
                    <Tag colorScheme="orange">±{data.updated_subscriptions.length}</Tag>
                  </HStack>
                  <Stack spacing={2}>
                    {data.updated_subscriptions.map(renderUpdatedCard)}
                  </Stack>
                </Box>
              )}
            </Stack>
          )}
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  )
}
