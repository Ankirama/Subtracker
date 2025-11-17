import apiClient from './client'

export interface Category {
  id: string | null  // null for default categories
  name: string
  display_name: string
  color: string
  is_default: boolean
  user_id: string | null  // null for default categories
  created_at: string | null
  updated_at: string | null
}

export interface CategoryCreate {
  name: string
  display_name: string
  color?: string  // Optional, defaults to 'gray' if not specified
}

export interface CategoriesListResponse {
  categories: Category[]
  total: number
}

export const categoriesAPI = {
  /**
   * Get all categories (default + custom)
   */
  async getAll(): Promise<CategoriesListResponse> {
    const response = await apiClient.get('/categories')
    return response.data
  },

  /**
   * Create a new custom category
   */
  async create(data: CategoryCreate): Promise<Category> {
    const response = await apiClient.post('/categories', data)
    return response.data
  },

  /**
   * Delete a custom category
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/categories/${id}`)
  },
}
