import React from 'react';
import {observer} from 'mobx-react';
import bem, {makeBem} from 'js/bem';
import sessionStore from 'js/stores/session';
import {replaceBracketsWithLink} from 'js/utils';

import envStore from 'js/envStore';
import './accessDenied.scss';

bem.AccessDenied = makeBem(null, 'access-denied');
bem.AccessDenied__body = makeBem(bem.AccessDenied, 'body', 'section');
bem.AccessDenied__header = makeBem(bem.AccessDenied, 'header', 'header');
bem.AccessDenied__text = makeBem(bem.AccessDenied, 'text', 'section');

export interface AccessDeniedProps {
  errorMessage?: string;
}
const AccessDenied = (props: AccessDeniedProps) => {
  let messageText;
  let headerText;
  let bodyText;
  let errorNumber;
  const loggedIn = t(
    `Please [contact the support team] if you think it's an error.`
  );
  const loggedOut = t(
    `Please try logging in using the header button or [contact the support team] if you think it's an error.`
  );

  // Obtaining error message number
  if(props.errorMessage){
    errorNumber = parseInt(props.errorMessage.replace( /[^\d].*/, '' ));
  }
  else{
    errorNumber = 404;
  }
  
  // Conditionally rendering error message based on number
  switch (errorNumber){
    case 403 || 401:
      headerText = t(`Access Denied`);
      bodyText = t(`You don't have access to this page.`);
      if (sessionStore.isLoggedIn) {
        messageText = loggedIn;
      } else {
        messageText = loggedOut;
      }
      break;
    case 404:
      headerText = t(`Access Denied`);
      bodyText = t(`Either you don't have access to this page or this page simply doesn't exist.`);
      if (sessionStore.isLoggedIn) {
        messageText = loggedIn;
      } else {
        messageText = loggedOut;
      }
      break;
    default:
      headerText = t(`Something went wrong`);
      bodyText = t(`We're sorry, but there was an unexpected error while trying to serve this page.`);
      messageText = t(
        `Please try again later, or [contact the support team] if this happens repeatedly.`
      );
      break;
  }

  let messageHtml = replaceBracketsWithLink(
    messageText,
    envStore.data.support_url
  );

  return (
    <bem.AccessDenied>
      <bem.AccessDenied__body>
        <bem.AccessDenied__header>
          {errorNumber < 500 && 
            <i className='k-icon k-icon-lock-alt' />
          }
          {headerText}
        </bem.AccessDenied__header>

        <bem.AccessDenied__text>
          {bodyText}

          <p dangerouslySetInnerHTML={{__html: messageHtml}} />
        </bem.AccessDenied__text>

        {props.errorMessage && (
          <bem.AccessDenied__text>
            {t('Additional details:')}

            <code>{props.errorMessage}</code>
          </bem.AccessDenied__text>
        )}
      </bem.AccessDenied__body>
    </bem.AccessDenied>
  );
};

export default observer(AccessDenied);
