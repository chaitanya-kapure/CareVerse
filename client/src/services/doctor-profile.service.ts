import { api } from "./api";
import type {
  DoctorProfile,
  DoctorProfileUpdate,
  DoctorDiscoveryResponse,
  PatientDiscoveryResult,
  CareVerseIdResponse,
} from "../types";

export const doctorProfileService = {
  getMyProfile: async (): Promise<DoctorProfile> => {
    const res = await api.get("/doctor-profiles/me");
    return res.data;
  },
  updateMyProfile: async (data: DoctorProfileUpdate): Promise<DoctorProfile> => {
    const res = await api.patch("/doctor-profiles/me", data);
    return res.data;
  },
  getProfile: async (userId: string): Promise<DoctorProfile> => {
    const res = await api.get(`/doctor-profiles/${userId}`);
    return res.data;
  },
  discoverDoctors: async (params?: {
    specialty?: string;
    name?: string;
    verified_only?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<DoctorDiscoveryResponse> => {
    const res = await api.get("/doctor-profiles", { params });
    return res.data;
  },
  follow: async (userId: string): Promise<void> => {
    await api.post(`/social/follows/${userId}`);
  },
  unfollow: async (userId: string): Promise<void> => {
    await api.delete(`/social/follows/${userId}`);
  },
  lookupPatientByCareverseId: async (careVerseId: string): Promise<PatientDiscoveryResult> => {
    const res = await api.get(`/discovery/patient/${careVerseId}`);
    return res.data;
  },
  getMyCareverseId: async (): Promise<CareVerseIdResponse> => {
    const res = await api.get("/patients/me/careverse-id");
    return res.data;
  },
};
