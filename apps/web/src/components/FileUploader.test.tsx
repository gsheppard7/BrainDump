import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test/render'
import { FileUploader } from './FileUploader'

describe('FileUploader', () => {
  it('rejects unsupported and oversized files before uploading', async () => {
    const send = vi.spyOn(XMLHttpRequest.prototype, 'send').mockImplementation(() => {})
    renderWithProviders(<FileUploader maxBytes={10} />)
    const input = screen.getByTestId('file-input')

    await userEvent.upload(input, new File(['hi'], 'slides.pptx'), { applyAccept: false })
    expect(await screen.findByText(/\.pptx files aren't supported/)).toBeInTheDocument()

    await userEvent.upload(input, new File(['this is way too long'], 'big.txt'))
    expect(await screen.findByText(/maximum upload size is 10 B/)).toBeInTheDocument()

    expect(send).not.toHaveBeenCalled()
  })
})
