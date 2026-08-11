export type SessionStatus = 'active' | 'completed' | 'cancelled';

export interface ApiRequestOptions {
  readonly signal?: AbortSignal;
}

export interface HealthResponse {
  readonly status: 'ok';
  readonly service: string;
  readonly version: string;
}

export interface DeviceCreateRequest {
  readonly device_uid: string;
  readonly name?: string | null;
  readonly is_active?: boolean;
}

export interface DeviceStatusRequest {
  readonly is_active: boolean;
}

export interface DeviceResponse {
  readonly id: number;
  readonly device_uid: string;
  readonly name: string | null;
  readonly is_active: boolean;
  readonly created_at: string;
}

export interface SessionCreateRequest {
  readonly latitude: number;
  readonly longitude: number;
  readonly started_at?: string | null;
}

export interface SessionTransitionRequest {
  readonly ended_at?: string | null;
}

export interface SessionResponse {
  readonly id: number;
  readonly device_id: number;
  readonly status: SessionStatus;
  readonly started_at: string;
  readonly ended_at: string | null;
  readonly latitude: number;
  readonly longitude: number;
  readonly sample_count: number;
  readonly created_at: string;
}

export interface MeasurementCreateRequest {
  readonly measured_at: string;
  readonly source_message_id?: string | null;
  readonly temperature?: number | null;
  readonly humidity?: number | null;
  readonly pm1?: number | null;
  readonly pm25?: number | null;
  readonly pm10?: number | null;
  readonly pc0_3?: number | null;
  readonly pc0_5?: number | null;
  readonly pc1_0?: number | null;
  readonly pc2_5?: number | null;
  readonly pc5_0?: number | null;
  readonly pc10?: number | null;
  readonly latitude?: number | null;
  readonly longitude?: number | null;
  readonly is_valid?: boolean;
  readonly validation_note?: string | null;
}

export interface MeasurementResponse {
  readonly id: number;
  readonly device_id: number;
  readonly session_id: number;
  readonly source_message_id: string | null;
  readonly measured_at: string;
  readonly received_at: string;
  readonly temperature: number | null;
  readonly humidity: number | null;
  readonly pm1: number | null;
  readonly pm25: number | null;
  readonly pm10: number | null;
  readonly pc0_3: number | null;
  readonly pc0_5: number | null;
  readonly pc1_0: number | null;
  readonly pc2_5: number | null;
  readonly pc5_0: number | null;
  readonly pc10: number | null;
  readonly latitude: number | null;
  readonly longitude: number | null;
  readonly is_valid: boolean;
  readonly validation_note: string | null;
  readonly created_at: string;
}

export interface CursorPage<T> {
  readonly items: readonly T[];
  readonly next_cursor: string | null;
}

export interface SessionListQuery {
  readonly status?: SessionStatus;
  readonly started_from?: string;
  readonly started_to?: string;
  readonly limit?: number;
  readonly cursor?: string;
}

export interface MeasurementListQuery {
  readonly session_id?: number;
  readonly measured_from?: string;
  readonly measured_to?: string;
  readonly limit?: number;
  readonly cursor?: string;
}

export interface AirMonitorApi {
  getHealth(options?: ApiRequestOptions): Promise<HealthResponse>;
  createDevice(
    request: DeviceCreateRequest,
    options?: ApiRequestOptions,
  ): Promise<DeviceResponse>;
  getDevice(
    deviceId: number,
    options?: ApiRequestOptions,
  ): Promise<DeviceResponse>;
  setDeviceStatus(
    deviceId: number,
    request: DeviceStatusRequest,
    options?: ApiRequestOptions,
  ): Promise<DeviceResponse>;
  startSession(
    deviceId: number,
    request: SessionCreateRequest,
    options?: ApiRequestOptions,
  ): Promise<SessionResponse>;
  listSessions(
    deviceId: number,
    query?: SessionListQuery,
    options?: ApiRequestOptions,
  ): Promise<CursorPage<SessionResponse>>;
  getActiveSession(
    deviceId: number,
    options?: ApiRequestOptions,
  ): Promise<SessionResponse>;
  completeActiveSession(
    deviceId: number,
    request?: SessionTransitionRequest,
    options?: ApiRequestOptions,
  ): Promise<SessionResponse>;
  cancelActiveSession(
    deviceId: number,
    request?: SessionTransitionRequest,
    options?: ApiRequestOptions,
  ): Promise<SessionResponse>;
  recordMeasurement(
    deviceId: number,
    request: MeasurementCreateRequest,
    options?: ApiRequestOptions,
  ): Promise<MeasurementResponse>;
  listMeasurements(
    deviceId: number,
    query?: MeasurementListQuery,
    options?: ApiRequestOptions,
  ): Promise<CursorPage<MeasurementResponse>>;
}
