import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import './index.css'
import { AuthGate } from './components/AuthGate'
import { UserMenu } from './components/UserMenu'
import { RunPage } from './pages/RunPage'
import { RunsPage } from './pages/RunsPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <BrowserRouter>
        <header className="topbar">
          <Link to="/" className="brand">
            <img src="/favicon.svg" alt="" width={22} height={22} />
            Panbiome <span>Run Monitor</span>
          </Link>
          <UserMenu />
        </header>
        <Routes>
          <Route path="/" element={<RunsPage />} />
          <Route path="/runs/:run" element={<RunPage />} />
        </Routes>
      </BrowserRouter>
    </AuthGate>
  </StrictMode>,
)
