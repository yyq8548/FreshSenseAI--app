import {theme} from '../theme';

const technologies = ['Python', 'TensorFlow', 'FastAPI', 'React', 'PostgreSQL', 'Azure'];
export const TechStack: React.FC = () => <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 18}}>
  {technologies.map((name) => <span key={name} style={{font: `600 36px ${theme.font}`, color: theme.greenDark, border: `2px solid ${theme.green}`, borderRadius: 999, padding: '12px 22px'}}>{name}</span>)}
</div>;
