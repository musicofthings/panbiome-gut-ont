import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import './index.css'
import { AuthGate } from './components/AuthGate'
import { UserMenu } from './components/UserMenu'
import { FilesPage } from './pages/FilesPage'
import { ReportPage } from './pages/ReportPage'
import { RunPage } from './pages/RunPage'
import { RunsPage } from './pages/RunsPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <BrowserRouter>
        <header className="topbar">
          <Link to="/" className="brand">
            <img src="/favicon.svg" alt="" width={22} height={22} />
            Panbiome <span>Gut ONT</span>
          </Link>
          <nav className="main-nav">
            <NavLink to="/" end>
              Runs
            </NavLink>
            <NavLink to="/files">Files</NavLink>
          </nav>
          <UserMenu />
        </header>
        <Routes>
          <Route path="/" element={<RunsPage />} />
          <Route path="/runs/:run" element={<RunPage />} />
          <Route path="/runs/:run/report" element={<ReportPage />} />
          <Route path="/files" element={<FilesPage />} />
        </Routes>
      </BrowserRouter>
    </AuthGate>
  </StrictMode>,
)
