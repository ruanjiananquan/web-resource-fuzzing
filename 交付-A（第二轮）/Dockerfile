FROM php:8.2-apache
COPY . /var/www/lab-extra/
RUN a2enmod rewrite \
 && printf 'Alias /lab-extra /var/www/lab-extra\n<Directory /var/www/lab-extra>\n  DirectoryIndex index.php\n  AllowOverride All\n  Require all granted\n</Directory>\n' > /etc/apache2/conf-available/lab-extra.conf \
 && a2enconf lab-extra
EXPOSE 80
