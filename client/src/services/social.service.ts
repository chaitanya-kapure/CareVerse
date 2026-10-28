import { api } from "./api";
import type { Post, PostListResponse, CreatePostPayload, CommentListResponse } from "../types";

export const socialService = {
  listPosts: async (skip = 0, limit = 20): Promise<PostListResponse> => {
    const res = await api.get("/social/posts", { params: { skip, limit } });
    return res.data;
  },
  createPost: async (payload: CreatePostPayload): Promise<Post> => {
    const res = await api.post("/social/posts", payload);
    return res.data;
  },
  deletePost: async (postId: string): Promise<void> => {
    await api.delete(`/social/posts/${postId}`);
  },
  toggleLike: async (postId: string): Promise<void> => {
    await api.post(`/social/posts/${postId}/like`);
  },
  toggleSave: async (postId: string): Promise<void> => {
    await api.post(`/social/posts/${postId}/save`);
  },
  reportPost: async (postId: string, reason: string): Promise<void> => {
    await api.post(`/social/posts/${postId}/report`, { reason });
  },
  listComments: async (postId: string): Promise<CommentListResponse> => {
    const res = await api.get(`/social/posts/${postId}/comments`);
    return res.data;
  },
  addComment: async (postId: string, content: string): Promise<void> => {
    await api.post(`/social/posts/${postId}/comments`, { content });
  },
  deleteComment: async (postId: string, commentId: string): Promise<void> => {
    await api.delete(`/social/posts/${postId}/comments/${commentId}`);
  },
};
