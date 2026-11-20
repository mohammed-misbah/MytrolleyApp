import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Eye, EyeOff, Lock, User } from 'lucide-react'
import { toast } from 'sonner'
import logo from '@/assets/mytrolley_logo_original.png'
import { useAuth } from '@/hooks/useAuth'
import { toError } from '@/services/apiClient'
import { loginSchema, type LoginValues } from '@/schemas'

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
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
    <div className="mt-login">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400..600&display=swap');

        .mt-login {
          box-sizing: border-box;
          width: 100%;
          min-height: 100vh;
          min-height: 100dvh;
          background-color: #17382F;
          background-image: url('/assets/login-bg.png');
          background-size: cover;
          background-position: center;
          background-repeat: no-repeat;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          overflow: hidden;
          font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
          color: #FFFFFF;
          -webkit-font-smoothing: antialiased;
          text-rendering: optimizeLegibility;
        }
        .mt-login *, .mt-login *::before, .mt-login *::after { box-sizing: border-box; }

        .mt-login-card {
          width: 460px;
          max-width: calc(100vw - 32px);
          padding: 40px 40px 36px;
          border-radius: 28px;
          display: flex;
          flex-direction: column;
          background: linear-gradient(145deg, rgba(255,255,255,.12) 0%, rgba(255,255,255,.04) 100%);
          backdrop-filter: blur(16px) saturate(120%);
          -webkit-backdrop-filter: blur(16px) saturate(120%);
          border: 1px solid rgba(255,255,255,.18);
          box-shadow: 0 24px 70px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.22);
        }

        .mt-login-logo {
          width: 190px;
          height: auto;
          display: block;
          align-self: center;
        }

        .mt-login-subtitle {
          margin: 24px 0 0;
          font-size: 14.5px;
          font-weight: 400;
          letter-spacing: .01em;
          line-height: 1.4;
          text-align: center;
          color: rgba(255,255,255,.72);
        }

        .mt-login-form {
          width: 100%;
          display: flex;
          flex-direction: column;
        }

        .mt-login-label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          color: rgba(255,255,255,.88);
        }
        .mt-login-label-username { margin: 30px 0 8px; }
        .mt-login-label-password { margin: 20px 0 8px; }

        .mt-login-field {
          height: 56px;
          border-radius: 14px;
          background: rgba(255,255,255,.08);
          border: 1px solid rgba(255,255,255,.18);
          padding: 0 18px;
          display: flex;
          align-items: center;
          gap: 12px;
          transition: border-color .15s ease, box-shadow .15s ease;
        }
        .mt-login-field:focus-within {
          border-color: rgba(255,255,255,.55);
          box-shadow: 0 0 0 4px rgba(255,255,255,.10);
        }
        .mt-login-icon {
          flex: none;
          color: rgba(255,255,255,.85);
          stroke-linecap: round;
          stroke-linejoin: round;
        }
        .mt-login-input {
          flex: 1 1 auto;
          min-width: 0;
          width: 100%;
          height: 100%;
          padding: 0;
          margin: 0;
          background: transparent;
          border: none;
          outline: none;
          font-family: inherit;
          font-size: 16px;
          font-weight: 500;
          color: #FFFFFF;
        }
        .mt-login-input::placeholder { color: rgba(255,255,255,.60); opacity: 1; }
        .mt-login-input[type='password'] { letter-spacing: 2px; }
        .mt-login-eye {
          margin-left: auto;
          flex: none;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          background: none;
          border: none;
          color: rgba(255,255,255,.85);
          cursor: pointer;
        }

        .mt-login-submit {
          width: 100%;
          height: 58px;
          margin-top: 26px;
          border-radius: 999px;
          font-family: inherit;
          font-size: 17px;
          font-weight: 600;
          letter-spacing: .2px;
          color: #FFFFFF;
          background: linear-gradient(180deg, rgba(255,255,255,.28) 0%, rgba(255,255,255,.14) 100%);
          border: 1px solid rgba(255,255,255,.32);
          box-shadow: 0 10px 26px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.35);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          cursor: pointer;
        }
        .mt-login-submit:hover {
          background: linear-gradient(180deg, rgba(255,255,255,.36) 0%, rgba(255,255,255,.20) 100%);
        }
        .mt-login-submit:active { transform: translateY(1px); }
        .mt-login-submit:disabled { opacity: .6; cursor: default; }
        .mt-login-spinner {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          border: 2px solid rgba(255,255,255,.45);
          border-top-color: #FFFFFF;
          animation: mt-login-spin .7s linear infinite;
        }
        @keyframes mt-login-spin { to { transform: rotate(360deg); } }

        .mt-login-error {
          margin: 14px 0 0;
          text-align: center;
          font-size: 13.5px;
          font-weight: 400;
          color: #FFC2C2;
        }

        @media (max-width: 639px) {
          .mt-login-card {
            width: calc(100% - 32px);
            padding: 30px 22px;
          }
          .mt-login-logo { width: 160px; }
          .mt-login-field { height: 52px; }
        }
      `}</style>

      <div className="mt-login-card">
        <img src={logo} alt="MY Trolley" className="mt-login-logo" />

        <p className="mt-login-subtitle">Sign in to access the admin dashboard.</p>

        <form className="mt-login-form" onSubmit={handleSubmit(onSubmit)} noValidate>
        <label className="mt-login-label mt-login-label-username" htmlFor="mt-login-username">
          Username
        </label>
        <div className="mt-login-field">
          <User className="mt-login-icon" size={20} strokeWidth={1.8} />
          <input
            id="mt-login-username"
            type="text"
            className="mt-login-input"
            placeholder="Your username"
            autoComplete="username"
            {...register('username')}
          />
        </div>

        <label className="mt-login-label mt-login-label-password" htmlFor="mt-login-password">
          Password
        </label>
        <div className="mt-login-field">
          <Lock className="mt-login-icon" size={20} strokeWidth={1.8} />
          <input
            id="mt-login-password"
            type={showPassword ? 'text' : 'password'}
            className="mt-login-input"
            placeholder="••••••••"
            autoComplete="current-password"
            {...register('password')}
          />
          <button
            type="button"
            className="mt-login-eye"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            onClick={() => setShowPassword((value) => !value)}
          >
            {showPassword ? <EyeOff size={20} strokeWidth={1.8} /> : <Eye size={20} strokeWidth={1.8} />}
          </button>
        </div>

        <button type="submit" className="mt-login-submit" disabled={submitting}>
          {submitting && <span className="mt-login-spinner" aria-hidden="true" />}
          Sign in
        </button>

        {errors.root?.message && (
          <p className="mt-login-error">{errors.root.message}</p>
        )}
        </form>
      </div>
    </div>
  )
}
