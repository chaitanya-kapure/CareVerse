import { api } from "./api";
import type { AccessRequest, AccessRequestListResponse, CreateAccessRequestPayload } from "../types";

export const accessRequestService = {
  create: async (payload: CreateAccessRequestPayload): Promise<AccessRequest> => {
    const res = await api.post("/access-requests", payload);
    return res.data;
  },
  listReceived: async (skip = 0, limit = 20): Promise<AccessRequestListResponse> => {
    const res = await api.get("/access-requests/received", { params: { skip, limit } });
    return res.data;
  },
  listSent: async (skip = 0, limit = 20): Promise<AccessRequestListResponse> => {
    const res = await api.get("/access-requests/sent", { params: { skip, limit } });
    return res.data;
  },
  approve: async (requestId: string): Promise<AccessRequest> => {
    const res = await api.patch(`/access-requests/${requestId}/approve`);
    return res.data;
  },
  reject: async (requestId: string, reason?: string): Promise<AccessRequest> => {
    const res = await api.patch(`/access-requests/${requestId}/reject`, { reason });
    return res.data;
  },
};
