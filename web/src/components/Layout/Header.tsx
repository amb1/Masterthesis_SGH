import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';

export function Header() {
  const { signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="bg-white shadow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex justify-between items-center">
          <h1 
            className="text-2xl font-bold text-gray-900 cursor-pointer" 
            onClick={() => navigate('/')}
          >
            Ambi
          </h1>
          <Button variant="ghost" onClick={() => signOut()}>
            Abmelden
          </Button>
        </div>
      </div>
    </header>
  );
}