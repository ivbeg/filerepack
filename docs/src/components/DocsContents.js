import React from 'react';
import Link from '@docusaurus/Link';
import styles from './DocsContents.module.css';

const sections = [
  {
    title: 'Getting Started',
    to: '/getting-started/installation',
    description: 'Install filerepack and complete a first lossless repack.',
    links: [
      {label: 'Installation', to: '/getting-started/installation'},
      {label: 'Quick start', to: '/getting-started/quick-start'},
      {label: 'When to use', to: '/getting-started/when-to-use'},
      {label: 'Cookbook', to: '/getting-started/cookbook'},
      {label: 'Basic usage', to: '/getting-started/basic-usage'},
      {label: 'Safety', to: '/getting-started/safety'},
      {label: 'Troubleshooting', to: '/getting-started/troubleshooting'},
      {label: 'Best practices', to: '/getting-started/best-practices'},
    ],
  },
  {
    title: 'Use Cases',
    to: '/use-cases/office-documents',
    description: 'End-to-end examples for Office, archives, images, PDFs, bulk jobs, and data files.',
    links: [
      {label: 'Office documents', to: '/use-cases/office-documents'},
      {label: 'Archives', to: '/use-cases/archives'},
      {label: 'Images and media', to: '/use-cases/images-and-media'},
      {label: 'PDFs', to: '/use-cases/pdfs'},
      {label: 'Bulk directories', to: '/use-cases/bulk-directories'},
      {label: 'Data files', to: '/use-cases/data-files'},
    ],
  },
  {
    title: 'CLI Reference',
    to: '/commands/',
    description: 'Command-by-command reference for repack, bulk, and doctor.',
    links: [
      {label: 'All commands', to: '/commands/'},
      {label: 'Shared options', to: '/commands/shared-options'},
      {label: 'repack', to: '/commands/repack'},
      {label: 'bulk', to: '/commands/bulk'},
      {label: 'doctor', to: '/commands/doctor'},
    ],
  },
  {
    title: 'Formats and tools',
    to: '/formats/',
    description: 'Format coverage, nested walking, and the external binaries each packer needs.',
    links: [
      {label: 'Format support matrix', to: '/formats/'},
      {label: 'External tools', to: '/tools/'},
      {label: 'doctor command', to: '/commands/doctor'},
    ],
  },
  {
    title: 'Library',
    to: '/library/',
    description: 'Call FileRepacker from Python with the same options as the CLI.',
    links: [
      {label: 'Python API', to: '/library/'},
      {label: 'RepackOptions', to: '/library/#options'},
      {label: 'Format helpers', to: '/library/#format-helpers'},
    ],
  },
  {
    title: 'Development',
    to: '/development/contributing',
    description: 'Contributing, tests, and license.',
    links: [
      {label: 'Contributing', to: '/development/contributing'},
      {label: 'License', to: '/license'},
    ],
  },
];

function Section({title, to, description, links}) {
  return (
    <article className={styles.card}>
      <h3 className={styles.cardTitle}>
        <Link to={to}>{title}</Link>
      </h3>
      <p className={styles.cardDescription}>{description}</p>
      <ul className={styles.linkList}>
        {links.map((item) => (
          <li key={item.label}>
            {item.href ? (
              <a href={item.href}>{item.label}</a>
            ) : (
              <Link to={item.to}>{item.label}</Link>
            )}
          </li>
        ))}
      </ul>
    </article>
  );
}

export default function DocsContents() {
  return (
    <section className={styles.contents}>
      <div className="container">
        <h2 className={styles.heading}>Documentation contents</h2>
        <p className={styles.intro}>
          Start with a section below, or use the sidebar from any page. The CLI
          entry point is <code>filerepack</code>.
        </p>
        <div className={styles.grid}>
          {sections.map((section) => (
            <Section key={section.title} {...section} />
          ))}
        </div>
      </div>
    </section>
  );
}
