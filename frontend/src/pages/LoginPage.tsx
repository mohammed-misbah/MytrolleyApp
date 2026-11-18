import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Lock, User, Leaf } from 'lucide-react'
import { toast } from 'sonner'
import logo from '@/assets/logo.png'
import { Button } from '@/components/ui/button'
import { Input, Field } from '@/components/ui/field'
import { useAuth } from '@/hooks/useAuth'
import { toError } from '@/services/apiClient'
import { loginSchema, type LoginValues } from '@/schemas'

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  const onSubmit = async (values: LoginValues) => {
    setSubmitting(true)
    try {
      await signIn(values.username, values.password)
      toast.success('Signed in successfully.')
      navigate('/dashboard', { replace: true })
    } catch (error) {
      const apiError = toError(error)
      if (apiError.code === 'RATE_LIMITED') {
        setError('root', { message: apiError.message + ' Please try again shortly.' })
      } else {
        setError('root', { message: apiError.message })
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="hidden w-1/2 flex-col justify-between bg-forest px-14 py-12 text-white lg:flex">
        <img src={logo} alt="MY Trolley" className="h-14 w-auto" />
        <div className="max-w-md space-y-5">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-lime">
            <Leaf className="h-3.5 w-3.5" /> Everything for you.
          </div>
          <h2 className="text-4xl font-semibold leading-tight">Product management, beautifully organised.</h2>
          <p className="text-sm leading-relaxed text-white/70">
            Manage products, categories, stores and store-specific inventory from one premium workspace
            built for the MY Trolley team.
          </p>
        </div>
        <p className="text-xs text-white/50">© {new Date().getFullYear()} MY Trolley</p>
      </div>

      <div className="flex flex-1 items-center justify-center bg-canvas px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <img src={logo} alt="MY Trolley" className="h-12 w-auto" />
          </div>
          <h1 className="text-2xl font-semibold text-ink">Welcome back</h1>
          <p className="mt-1 text-sm text-subtle">Sign in to access the admin dashboard.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-5">
            <Field label="Username" error={errors.username?.message}>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
                <Input className="pl-9" placeholder="Your username" autoComplete="username" {...register('username')} />
              </div>
            </Field>
            <Field label="Password" error={errors.password?.message}>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
                <Input type="password" className="pl-9" placeholder="••••••••" autoComplete="current-password" {...register('password')} />
              </div>
            </Field>
            {errors.root?.message && (
              <p className="rounded-control bg-danger/10 px-3 py-2 text-sm text-danger">{errors.root.message}</p>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
