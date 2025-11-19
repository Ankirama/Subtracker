import { Box, BoxProps } from '@chakra-ui/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import DOMPurify from 'dompurify'

interface MarkdownRendererProps extends BoxProps {
  content: string
}

export const MarkdownRenderer = ({ content, ...boxProps }: MarkdownRendererProps) => {
  // Sanitize the content first
  const sanitizedContent = DOMPurify.sanitize(content)

  return (
    <Box
      {...boxProps}
      sx={{
        '& p': {
          marginBottom: '0.5em',
        },
        '& h1': {
          fontSize: '2xl',
          fontWeight: 'bold',
          marginTop: '0.5em',
          marginBottom: '0.5em',
        },
        '& h2': {
          fontSize: 'xl',
          fontWeight: 'bold',
          marginTop: '0.5em',
          marginBottom: '0.5em',
        },
        '& h3': {
          fontSize: 'lg',
          fontWeight: 'bold',
          marginTop: '0.5em',
          marginBottom: '0.5em',
        },
        '& ul, & ol': {
          marginLeft: '1.5em',
          marginBottom: '0.5em',
        },
        '& li': {
          marginBottom: '0.25em',
        },
        '& code': {
          backgroundColor: 'gray.100',
          padding: '0.2em 0.4em',
          borderRadius: '3px',
          fontSize: '0.9em',
          fontFamily: 'monospace',
        },
        '& pre': {
          backgroundColor: 'gray.100',
          padding: '1em',
          borderRadius: '5px',
          overflow: 'auto',
          marginBottom: '0.5em',
        },
        '& pre code': {
          backgroundColor: 'transparent',
          padding: 0,
        },
        '& blockquote': {
          borderLeft: '4px solid',
          borderColor: 'gray.300',
          paddingLeft: '1em',
          marginLeft: 0,
          fontStyle: 'italic',
          color: 'gray.600',
        },
        '& a': {
          color: 'blue.500',
          textDecoration: 'underline',
        },
        '& strong': {
          fontWeight: 'bold',
        },
        '& em': {
          fontStyle: 'italic',
        },
        '& hr': {
          borderColor: 'gray.300',
          marginTop: '1em',
          marginBottom: '1em',
        },
      }}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{sanitizedContent}</ReactMarkdown>
    </Box>
  )
}
