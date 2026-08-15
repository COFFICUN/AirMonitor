import { describe, expect, it } from 'vitest';

import { ApiError } from './errors';
import { apiErrorMessage } from './presentation';

describe('apiErrorMessage', () => {
  it('uses localized messages for known backend codes', () => {
    expect(
      apiErrorMessage(
        new ApiError({
          kind: 'http',
          status: 404,
          code: 'device_not_found',
          publicMessage: 'Device was not found.',
        }),
      ),
    ).toBe('Устройство не найдено. Проверьте ID.');
  });

  it('preserves a client-validated safe backend message for unknown codes', () => {
    expect(
      apiErrorMessage(
        new ApiError({
          kind: 'http',
          status: 409,
          code: 'future_safe_conflict',
          publicMessage: 'The requested transition is unavailable.',
        }),
        'Fallback',
      ),
    ).toBe('The requested transition is unavailable.');
  });
});
