import React from 'react';
import MfaSection from './mfa/mfaSection.component';
import style from './securityRoute.module.scss';

export default function securityRoute() {
  return (
    <div className={style['security-section']}>
      <h1>Security</h1>
      <MfaSection />
    </div>
  );
}
