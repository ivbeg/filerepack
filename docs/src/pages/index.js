import React from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import DocsContents from '@site/src/components/DocsContents';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  const logoSrc = useBaseUrl('img/logo.svg');
  return (
    <header className={styles.hero}>
      <div className="container">
        <img className={styles.heroLogo} src={logoSrc} alt="" width={72} height={72} />
        <h1 className={styles.heroTitle}>{siteConfig.title}</h1>
        <p className={styles.heroTagline}>{siteConfig.tagline}</p>
        <p className={styles.heroNote}>
          Nested files inside ZIP, 7z, RAR, and OOXML are walked and optimized,
          then the container is rewritten. Output that is not smaller is discarded.
        </p>
        <pre className={styles.install}>
          {'pip install filerepack\nfilerepack repack document.docx'}
        </pre>
      </div>
    </header>
  );
}

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout title="Documentation" description={siteConfig.tagline}>
      <HomepageHeader />
      <main>
        <DocsContents />
      </main>
    </Layout>
  );
}
