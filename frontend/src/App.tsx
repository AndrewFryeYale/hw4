import { Link, Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar'
import AnnouncementBar from './components/AnnouncementBar'
import ChatWidget from './components/ChatWidget'
import Home from './pages/Home'
import Products from './pages/Products'
import ProductDetail from './pages/ProductDetail'
import About from './pages/About'
import Login from './pages/Login'
import CreateAccount from './pages/CreateAccount'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <>
      <NavBar />
      <AnnouncementBar />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route path="/create-account" element={<CreateAccount />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="footer">
        <div className="footer-inner">
          <div>
            <p className="footer-brand">Campus Customs</p>
            <p>Officially licensed Yale apparel and gifts, a short walk from Old Campus.</p>
          </div>
          <div>
            <p className="footer-heading">Visit the shop</p>
            <p>57 Broadway, New Haven, CT 06511</p>
            <a href="https://www.google.com/maps/search/?api=1&query=57+Broadway+New+Haven+CT+06511" target="_blank" rel="noreferrer">
              Get directions →
            </a>
          </div>
          <div>
            <p className="footer-heading">Shop</p>
            <Link to="/products?category=Hoodies">Hoodies</Link>
            <Link to="/products?category=Crewnecks">Crewnecks</Link>
            <Link to="/products?category=Tees%20%26%20shirts">Tees &amp; shirts</Link>
            <Link to="/products">Everything</Link>
          </div>
        </div>
        <p className="footer-fine">Boola Boola · Made for Bulldogs everywhere</p>
      </footer>
      <ChatWidget />
    </>
  )
}
