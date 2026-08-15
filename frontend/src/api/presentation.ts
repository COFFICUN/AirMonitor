import { isApiError } from './errors';

const CODE_MESSAGES: Readonly<Record<string, string>> = {
  device_not_found: 'Устройство не найдено. Проверьте ID.',
  duplicate_device_uid: 'Устройство с таким UID уже зарегистрировано.',
  device_inactive: 'Устройство неактивно. Сначала активируйте его.',
  active_session_already_exists: 'У устройства уже есть активная сессия.',
  active_session_not_found: 'Активная сессия не найдена.',
  invalid_session_transition: 'Состояние сессии изменилось. Обновите данные.',
  invalid_timestamp: 'Время операции не согласуется с текущей сессией.',
  request_validation_error: 'Проверьте введённые данные.',
};

export function apiErrorMessage(
  error: unknown,
  fallback = 'Не удалось выполнить запрос.',
): string {
  if (!isApiError(error)) {
    return fallback;
  }
  const codeMessage =
    error.code === undefined ? undefined : CODE_MESSAGES[error.code];
  if (codeMessage !== undefined) {
    return codeMessage;
  }
  switch (error.kind) {
    case 'network':
      return 'Не удалось связаться с сервером.';
    case 'timeout':
      return 'Сервер не ответил вовремя.';
    case 'invalid_response':
      return 'Сервер вернул неожиданный ответ.';
    case 'http':
      return error.publicMessage ?? fallback;
    case 'aborted':
      return fallback;
  }
}
