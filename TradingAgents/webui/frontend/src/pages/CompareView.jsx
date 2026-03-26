import { useParams } from 'react-router-dom';

export default function CompareView() {
  const { id, id2 } = useParams();
  return (
    <div>
      <h2 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
        Compare: {id} vs {id2}
      </h2>
    </div>
  );
}
