import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Eye, EyeOff, Lock, User } from 'lucide-react'
import { toast } from 'sonner'
import logo from '@/assets/mytrolley_logo_brand.png'
import tcart from '@/assets/MyTrolley_T-cart_icon.png'
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
        .mt-login {
          position: relative;
          width: 100vw;
          height: 100vh;
          overflow: hidden;
          background: #D8D8D8;
          font-family: Inter, ui-sans-serif, system-ui, sans-serif;
        }
        .mt-login-panel {
          position: absolute;
          inset: 0;
          background: #0E3D28;
          clip-path: polygon(50.8% 0, 100% 0, 100% 100%, 30% 100%);
        }
        .mt-login-cart {
          position: absolute;
          right: 3vw;
          bottom: 4vh;
          width: min(42vw, 76vh);
          height: auto;
          object-fit: contain;
          z-index: 1;
          filter: drop-shadow(0 30px 60px rgba(0,0,0,.35));
        }
        .mt-login-logo {
          position: absolute;
          left: 5.3vw;
          top: 5vh;
          width: 220px;
          height: auto;
          object-fit: contain;
          z-index: 3;
        }
        .mt-login-card {
          position: absolute;
          left: 3.6vw;
          top: 20.8vh;
          width: 39.5vw;
          min-width: 440px;
          max-width: 760px;
          min-height: 70vh;
          padding: 56px 48px;
          border-radius: 48px;
          z-index: 2;
          background: rgba(255,255,255,.18);
          backdrop-filter: blur(22px);
          -webkit-backdrop-filter: blur(22px);
          border: 1px solid rgba(255,255,255,.35);
          box-shadow: 0 20px 60px rgba(0,0,0,.12), inset 0 1px 0 rgba(255,255,255,.5);
          box-sizing: border-box;
        }
        .mt-login-title {
          margin: 0 0 56px;
          text-align: center;
          font-size: 40px;
          font-weight: 600;
          color: #111111;
          letter-spacing: -.5px;
        }
        .mt-login-subtitle {
          margin: -40px 0 28px;
          text-align: center;
          font-size: 14px;
          color: #111111;
        }
        .mt-login-label {
          display: block;
          margin: 0 0 10px;
          font-size: 14px;
          font-weight: 600;
          color: #111111;
        }
        .mt-login-fieldwrap { position: relative; margin-bottom: 28px; }
        .mt-login-icon {
          position: absolute;
          left: 32px;
          top: 50%;
          transform: translateY(-50%);
          color: #7A7A7A;
          pointer-events: none;
        }
        .mt-login-input {
          width: 100%;
          height: 64px;
          border: none;
          border-radius: 20px;
          background: #C9C9C9;
          padding: 0 32px 0 64px;
          font-size: 18px;
          color: #7A7A7A;
          box-shadow: inset 0 2px 4px rgba(0,0,0,.08), 0 1px 0 rgba(255,255,255,.5);
          outline: none;
          box-sizing: border-box;
        }
        .mt-login-input::placeholder { color: #7A7A7A; }
        .mt-login-input:focus { outline: 2px solid rgba(14,61,40,.55); }
        .mt-login-eye {
          position: absolute;
          right: 24px;
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          padding: 0;
          color: #6A6A6A;
          cursor: pointer;
        }
        .mt-login-forgot {
          display: block;
          margin-top: 10px;
          font-size: 14px;
          color: #777777;
          text-decoration: underline;
        }
        .mt-login-error {
          margin-bottom: 10px;
          border-radius: 12px;
          padding: 10px 14px;
          font-size: 14px;
          color: #111111;
          background: rgba(0,0,0,.06);
        }
        .mt-login-submit {
          display: block;
          width: 200px;
          height: 56px;
          margin: 22px auto 0;
          border: none;
          border-radius: 999px;
          background: #0E3D28;
          color: #FFFFFF;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          box-shadow: 0 10px 24px rgba(14,61,40,.35), inset 0 1px 0 rgba(255,255,255,.12);
        }
        .mt-login-submit:hover { background: #124A31; }
        .mt-login-submit:disabled { opacity: .6; cursor: default; }
        .mt-login-signup {
          display: block;
          margin: 18px auto 0;
          text-align: center;
          font-size: 15px;
          color: #3B6FE0;
          text-decoration: underline;
        }
        .mt-login-social {
          display: flex;
          justify-content: center;
          gap: 28px;
          margin-top: 22px;
        }
        .mt-login-social button {
          width: 28px;
          height: 28px;
          border: none;
          background: none;
          padding: 0;
          font-size: 22px;
          font-weight: 700;
          cursor: default;
        }
        .mt-login-google { color: #4285F4; }
        .mt-login-facebook { color: #1877F2; }
        .mt-login-hidden { display: none; }
        @media (max-width: 1023px) {
          .mt-login-panel, .mt-login-cart { display: none; }
          .mt-login-logo {
            left: 50%;
            transform: translateX(-50%);
            top: 4vh;
          }
          .mt-login-card {
            left: 50%;
            top: 18vh;
            transform: translateX(-50%);
            width: calc(100% - 32px);
            min-width: 0;
            max-width: 520px;
            min-height: 0;
            padding: 36px 28px;
          }
          .mt-login-title { font-size: 32px; margin-bottom: 36px; }
          .mt-login-subtitle { margin-top: -28px; }
        }
      `}</style>

      <div className="mt-login-panel">
        <img src={tcart} alt="" className="mt-login-cart" />
      </div>

      <img src={logo} alt="MY Trolley" className="mt-login-logo" />

      <div className="mt-login-hidden">
        <div>Everything for you.</div>
        <h2>Product management, beautifully organised.</h2>
        <p>
          Manage products, categories, stores and store-specific inventory from one premium workspace
          built for the MY Trolley team.
        </p>
        <p>© {new Date().getFullYear()} MY Trolley</p>
      </div>

      <div className="mt-login-card">
        <h1 className="mt-login-title">Welcome back</h1>
        <p className="mt-login-subtitle">Sign in to access the admin dashboard.</p>

        <form onSubmit={handleSubmit(onSubmit)}>
          <label className="mt-login-label" htmlFor="mt-login-username">Username</label>
          <div className="mt-login-fieldwrap">
            <User className="mt-login-icon" size={18} strokeWidth={1.8} />
            <input
              id="mt-login-username"
              type="text"
              className="mt-login-input"
              placeholder="Your username"
              autoComplete="username"
              {...register('username')}
            />
          </div>

          <label className="mt-login-label" htmlFor="mt-login-password">Password</label>
          <div className="mt-login-fieldwrap">
            <Lock className="mt-login-icon" size={18} strokeWidth={1.8} />
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
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>

          <a className="mt-login-forgot" href="#" onClick={(event) => event.preventDefault()}>
            forgot password
          </a>

          {errors.root?.message && (
            <p className="mt-login-error">{errors.root.message}</p>
          )}

          <button type="submit" className="mt-login-submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>

          <a className="mt-login-signup" href="#" onClick={(event) => event.preventDefault()}>
            Sign up
          </a>

          <div className="mt-login-social">
            <button type="button" className="mt-login-google" aria-label="Google">G</button>
            <button type="button" className="mt-login-facebook" aria-label="Facebook">f</button>
          </div>
        </form>
      </div>
    </div>
  )
}
